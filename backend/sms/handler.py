"""Twilio inbound webhook + shared handler logic.

Handles text-only and MMS (photo) messages. Photo is the primary use case.
"""

import json
import logging
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, Form, Request, Response
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


@dataclass
class HandlerResult:
    """Result from handle_inbound_message — shared between Twilio and console."""

    action: str  # consent_request, opt_in, opt_out, observation, empty
    response_text: str = ""
    coaching_result: CoachingResult | None = None
    compliance_checks: dict = field(default_factory=dict)


def extract_media_urls(form_data: dict) -> list[str]:
    """Extract MMS media URLs from Twilio webhook form data.

    Twilio sends:
      NumMedia: "1"
      MediaUrl0: "https://api.twilio.com/2010-04-01/.../Media/ME..."
      MediaContentType0: "image/jpeg"

    Returns list of image URLs (filters to image/* content types only).
    """
    num_media = int(form_data.get("NumMedia", 0))
    urls = []
    for i in range(num_media):
        content_type = form_data.get(f"MediaContentType{i}", "")
        url = form_data.get(f"MediaUrl{i}", "")
        if url and content_type.startswith("image/"):
            urls.append(url)
    return urls


def _validate_twilio_signature(request: Request) -> bool:
    """Validate Twilio webhook signature."""
    if not settings.is_production:
        return True

    if not settings.twilio_auth_token:
        logger.warning("No Twilio auth token configured, skipping signature validation")
        return True

    from twilio.request_validator import RequestValidator

    validator = RequestValidator(settings.twilio_auth_token)
    url = str(request.url)
    signature = request.headers.get("X-Twilio-Signature", "")
    return validator.validate(url, {}, signature)


def _log_inbound(db: Session, phone: str, body: str, message_type: str, twilio_sid: str = ""):
    """Log an inbound message."""
    log = MessageLog(
        phone_hash=hash_phone(phone),
        direction="inbound",
        message_type=message_type,
        twilio_sid=twilio_sid,
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
    """Core message routing logic — shared between Twilio webhook and test console.

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
    worker_tier = 1  # TODO: calculate from rolling window once we have enough data
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

    # Run coaching engine (multi-turn aware)
    coaching_result = run_coaching(
        db=db,
        observation_text=body,
        trade=trade,
        experience_level=experience,
        observation_id=obs.id,
        media_urls=media_urls,
        phone_hash=ph,
        worker_id=worker.id if worker else None,
        worker_tier=worker_tier,
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
async def inbound_sms(
    request: Request,
    db: Session = Depends(get_db),
    From: str = Form(""),
    Body: str = Form(""),
    MessageSid: str = Form(""),
    NumMedia: str = Form("0"),
):
    """Handle inbound SMS/MMS from Twilio webhook.

    Extracts text body AND media URLs (photos) from the form data.
    """
    phone = From
    body = Body.strip()
    sid = MessageSid

    if not phone:
        return Response(content="<Response></Response>", media_type="application/xml")

    # Extract MMS photos
    form_data = await request.form()
    form_dict = dict(form_data)
    media_urls = extract_media_urls(form_dict)

    handle_inbound_message(db, phone, body, sid, media_urls=media_urls)

    return Response(content="<Response></Response>", media_type="application/xml")
