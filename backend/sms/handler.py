"""Telnyx inbound webhook + shared handler logic.

Handles text-only and MMS (photo) messages. Photo is the primary use case.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.coaching.engine import CoachingResult, run_coaching
from backend.config import settings
from backend.database import get_db
from backend.models import ConsentRecord, MessageLog, Observation, Worker, hash_phone
from backend.sms.consent import (
    CONSENT_CONFIRMED_MSG,
    CONSENT_REQUEST_MSG,
    OPT_OUT_CONFIRMED_MSG,
    create_consent,
    get_consent_record,
    is_opt_in,
    is_opt_out,
    revoke_consent,
    verify_consent,
)
from backend.sms.sender import send_sms

logger = logging.getLogger(__name__)
router = APIRouter()

MEDIA_DIR = Path("media/observations")


@dataclass
class HandlerResult:
    """Result from handle_inbound_message — shared between Telnyx and console."""

    action: str  # consent_request, opt_in, opt_out, observation, empty
    response_text: str = ""
    coaching_result: CoachingResult | None = None
    compliance_checks: dict = field(default_factory=dict)


async def _download_media(url: str) -> str | None:
    """Download MMS media from Telnyx temporary URL and save locally.

    Telnyx media URLs expire — must download immediately on webhook receipt.
    Returns local file path or None if download fails.
    """
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15.0)
            resp.raise_for_status()
            # Determine extension from content-type
            ct = resp.headers.get("content-type", "image/jpeg")
            ext = "jpg" if "jpeg" in ct else ct.split("/")[-1]
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = MEDIA_DIR / filename
            filepath.write_bytes(resp.content)
            return str(filepath)
    except Exception as e:
        logger.error("Failed to download media from %s: %s", url, e)
        return None


def _validate_telnyx_signature(request: Request, body: bytes) -> bool:
    """Validate Telnyx webhook signature using ed25519.

    Telnyx sends `telnyx-signature-ed25519` and `telnyx-timestamp` headers.
    Full production validation requires PyNaCl for ed25519 verification.
    Currently skips in non-production; logs warning if public key is missing in prod.
    """
    if not settings.is_production:
        return True

    if not settings.telnyx_public_key:
        logger.warning("No Telnyx public key configured, skipping signature validation")
        return True

    try:
        # Ed25519 verification: timestamp + body signed with Telnyx public key
        # For production, install PyNaCl and verify:
        #   from nacl.signing import VerifyKey
        #   verify_key = VerifyKey(bytes.fromhex(settings.telnyx_public_key))
        #   verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        signature = request.headers.get("telnyx-signature-ed25519", "")
        timestamp = request.headers.get("telnyx-timestamp", "")
        if not signature or not timestamp:
            logger.warning("Missing Telnyx signature headers")
            return False
        # TODO: Add PyNaCl ed25519 verification before production launch
        logger.info("Telnyx signature headers present (full verification pending PyNaCl)")
        return True
    except Exception as e:
        logger.warning("Telnyx signature validation failed: %s", e)
        return False


def _log_inbound(db: Session, phone: str, body: str, message_type: str, message_sid: str = ""):
    """Log an inbound message."""
    log = MessageLog(
        phone_hash=hash_phone(phone),
        direction="inbound",
        message_type=message_type,
        twilio_sid=message_sid,  # Column name kept for migration compat; stores Telnyx ID
        content_preview=body[:160],
        status="received",
    )
    db.add(log)
    db.commit()


def handle_inbound_message(
    db: Session,
    phone: str,
    body: str,
    sid: str = "",
    media_urls: list[str] | None = None,
) -> HandlerResult:
    """Core message routing logic — shared between Telnyx webhook and test console.

    Returns HandlerResult with action taken, response text, and coaching metadata.
    Supports both text-only and MMS (photo) messages.
    """
    if not phone:
        return HandlerResult(action="empty")

    logger.info("Inbound SMS from phone_hash=%s, len=%d, photos=%d",
                hash_phone(phone)[:12], len(body), len(media_urls or []))

    # 1. Opt-out — process immediately
    if is_opt_out(body):
        _log_inbound(db, phone, body, "opt_out", sid)
        revoke_consent(db, phone)
        send_sms(db, phone, OPT_OUT_CONFIRMED_MSG, message_type="opt_out", skip_compliance=True)
        return HandlerResult(action="opt_out", response_text=OPT_OUT_CONFIRMED_MSG)

    # 2. Check existing consent state
    consent = get_consent_record(db, phone)

    # 3. Opt-in confirmation (pending or brand new)
    if is_opt_in(body) and (consent is None or (consent and not consent.is_active)):
        _log_inbound(db, phone, body, "consent", sid)
        create_consent(db, phone)
        send_sms(db, phone, CONSENT_CONFIRMED_MSG, message_type="consent")
        return HandlerResult(action="opt_in", response_text=CONSENT_CONFIRMED_MSG)

    # 4. New number, no consent — start double opt-in
    if not verify_consent(db, phone):
        _log_inbound(db, phone, body, "new_contact", sid)
        ph = hash_phone(phone)
        pending = ConsentRecord(
            phone_hash=ph,
            consent_type="sms_coaching",
            consent_method="sms_double_optin",
            is_active=False,
        )
        db.add(pending)
        db.commit()
        send_sms(db, phone, CONSENT_REQUEST_MSG, message_type="consent", skip_compliance=True)
        return HandlerResult(action="consent_request", response_text=CONSENT_REQUEST_MSG)

    # 5. Active consent — create observation + run coaching engine
    _log_inbound(db, phone, body, "observation", sid)
    logger.info("Observation received from phone_hash=%s, has_photo=%s",
                hash_phone(phone)[:12], bool(media_urls))

    # Look up worker for trade/experience context
    ph = hash_phone(phone)
    worker = db.query(Worker).filter(Worker.phone_hash == ph).first()
    trade = worker.trade if worker else None
    experience = worker.experience_level if worker else "entry"
    preferred_language = worker.preferred_language if worker else "en"

    # Create observation record (with media URLs if present)
    obs = Observation(
        worker_id=worker.id if worker else None,
        raw_text=body,
        media_urls=json.dumps(media_urls) if media_urls else None,
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    # Run coaching engine (multi-turn aware, tier resolved from profile)
    coaching_result = run_coaching(
        db=db,
        observation_text=body,
        trade=trade,
        experience_level=experience,
        observation_id=obs.id,
        media_urls=media_urls,
        phone_hash=ph,
        worker_id=worker.id if worker else None,
        preferred_language=preferred_language,
    )

    # Send coaching response
    send_sms(db, phone, coaching_result.response_text, message_type="coaching")

    return HandlerResult(
        action="observation",
        response_text=coaching_result.response_text,
        coaching_result=coaching_result,
    )


@router.post("/inbound")
async def inbound_sms(request: Request, db: Session = Depends(get_db)):
    """Handle inbound SMS/MMS from Telnyx webhook.

    Telnyx sends JSON (not form data). Media URLs are temporary —
    photos must be downloaded immediately.
    """
    body = await request.json()
    event_type = body.get("data", {}).get("event_type", "")

    # Only process incoming messages; ignore delivery reports, etc.
    if event_type != "message.received":
        return JSONResponse(content={"status": "ignored"})

    payload = body["data"]["payload"]
    phone = payload.get("from", {}).get("phone_number", "")
    text = payload.get("text", "").strip()
    message_id = payload.get("id", "")

    if not phone:
        return JSONResponse(content={"status": "ignored"})

    # Extract and download MMS media (Telnyx URLs are temporary)
    media = payload.get("media", [])
    media_urls = [
        m["url"] for m in media
        if m.get("content_type", "").startswith("image/")
    ]

    stored_urls = []
    for url in media_urls:
        local_path = await _download_media(url)
        if local_path:
            stored_urls.append(local_path)

    handle_inbound_message(db, phone, text, message_id, media_urls=stored_urls or None)

    return JSONResponse(content={"status": "ok"})
