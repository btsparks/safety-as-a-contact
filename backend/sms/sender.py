"""Outbound SMS sender with compliance checks."""

import logging

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import MessageLog, hash_phone
from backend.sms.compliance import validate_outbound_message
from backend.sms.consent import verify_consent

logger = logging.getLogger(__name__)


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
        dict with status and optional twilio_sid or error.
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

    # Send via Twilio (or log-only in dev without credentials)
    twilio_sid = ""
    status = "sent"

    if settings.twilio_account_sid and settings.twilio_auth_token:
        try:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            kwargs = {"body": body, "to": to_phone}
            if settings.twilio_messaging_service_sid:
                kwargs["messaging_service_sid"] = settings.twilio_messaging_service_sid
            else:
                kwargs["from_"] = settings.twilio_phone_number

            message = client.messages.create(**kwargs)
            twilio_sid = message.sid
            logger.info("SMS sent to phone_hash=%s, sid=%s", ph[:12], twilio_sid)
        except Exception as e:
            logger.error("Twilio send failed for phone_hash=%s: %s", ph[:12], str(e))
            status = "failed"
    else:
        logger.info("DEV MODE — SMS logged (not sent) to phone_hash=%s: %s", ph[:12], body[:80])

    # Log to message_log
    log = MessageLog(
        phone_hash=ph,
        direction="outbound",
        message_type=message_type,
        twilio_sid=twilio_sid,
        content_preview=body[:160],
        status=status,
    )
    db.add(log)
    db.commit()

    return {"status": status, "twilio_sid": twilio_sid}
