"""Outbound SMS sender with compliance checks.

Uses Telnyx REST API directly via httpx (no SDK dependency).
"""

import logging

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import MessageLog, hash_phone
from backend.sms.compliance import validate_outbound_message
from backend.sms.consent import verify_consent

logger = logging.getLogger(__name__)

TELNYX_API_URL = "https://api.telnyx.com/v2/messages"


def send_sms(
    db: Session,
    to_phone: str,
    body: str,
    message_type: str = "system",
    skip_compliance: bool = False,
    hour: int | None = None,
) -> dict:
    """Send an SMS with full compliance checks.

    Args:
        db: Database session.
        to_phone: E.164 phone number.
        body: Message text.
        message_type: For logging (consent, opt_out, coaching, system).
        skip_compliance: True for opt-out confirmations and consent requests.
        hour: Override hour for sending window check (testing).

    Returns:
        dict with status and optional message_sid or error.
    """
    ph = hash_phone(to_phone)

    # Compliance checks (unless skipped for opt-out/consent messages)
    if not skip_compliance:
        # Consent check
        if not verify_consent(db, to_phone):
            logger.warning("Blocked send to phone_hash=%s — no consent", ph[:12])
            return {"status": "blocked", "reason": "no_consent"}

        # Sending window + rate limit
        ok, reason = validate_outbound_message(db, to_phone, hour=hour)
        if not ok:
            logger.warning("Blocked send to phone_hash=%s — %s", ph[:12], reason)
            return {"status": "blocked", "reason": reason}

    # Send via Telnyx REST API (or log-only in dev without credentials)
    message_sid = ""
    status = "sent"

    if settings.telnyx_api_key:
        try:
            payload = {
                "from": settings.telnyx_phone_number,
                "to": to_phone,
                "text": body,
            }
            if settings.telnyx_messaging_profile_id:
                payload["messaging_profile_id"] = settings.telnyx_messaging_profile_id

            resp = httpx.post(
                TELNYX_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.telnyx_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            message_sid = data.get("data", {}).get("id", "")
            logger.info("SMS sent to phone_hash=%s, sid=%s", ph[:12], message_sid)
        except Exception as e:
            logger.error("Telnyx send failed for phone_hash=%s: %s", ph[:12], str(e))
            status = "failed"
    else:
        logger.info("DEV MODE — SMS logged (not sent) to phone_hash=%s: %s", ph[:12], body[:80])

    # Log to message_log
    log = MessageLog(
        phone_hash=ph,
        direction="outbound",
        message_type=message_type,
        twilio_sid=message_sid,  # Column name kept for migration compat; stores Telnyx ID
        content_preview=body[:160],
        status=status,
    )
    db.add(log)
    db.commit()

    return {"status": status, "message_sid": message_sid}
