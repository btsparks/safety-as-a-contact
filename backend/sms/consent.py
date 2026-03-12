"""Consent management — opt-in, opt-out, verification."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models import ConsentRecord, hash_phone

logger = logging.getLogger(__name__)

# Opt-out keywords (case-insensitive)
OPT_OUT_KEYWORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}

# Opt-in keywords (case-insensitive)
OPT_IN_KEYWORDS = {"yes", "yep", "ok", "confirm", "start"}

# Double opt-in messages
CONSENT_REQUEST_MSG = (
    "Welcome to Safety as a Contact! We provide AI-powered safety coaching via text. "
    "Msg frequency varies. Msg&data rates may apply. "
    "Reply YES to opt in, STOP to cancel. Terms: safetyasacontact.com/sms-terms"
)

CONSENT_CONFIRMED_MSG = (
    "You're in! Text us anytime you spot a hazard on the job. "
    "We'll coach you through it. Reply STOP anytime to opt out. "
    "- Safety as a Contact"
)

OPT_OUT_CONFIRMED_MSG = (
    "You've been unsubscribed from Safety as a Contact. "
    "You won't receive more messages. Reply START to re-opt in."
)


def is_opt_out(message: str) -> bool:
    """Check if message is an opt-out keyword."""
    return message.strip().lower() in OPT_OUT_KEYWORDS


def is_opt_in(message: str) -> bool:
    """Check if message is an opt-in confirmation keyword."""
    return message.strip().lower() in OPT_IN_KEYWORDS


def verify_consent(db: Session, phone: str, consent_type: str = "sms_coaching") -> bool:
    """Check if phone has active consent. Returns True if consented."""
    ph = hash_phone(phone)
    record = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.phone_hash == ph,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.is_active == True,  # noqa: E712
        )
        .first()
    )
    return record is not None


def get_consent_record(db: Session, phone: str) -> ConsentRecord | None:
    """Get the most recent consent record for a phone number."""
    ph = hash_phone(phone)
    return (
        db.query(ConsentRecord)
        .filter(ConsentRecord.phone_hash == ph)
        .order_by(ConsentRecord.created_at.desc())
        .first()
    )


def create_consent(
    db: Session,
    phone: str,
    consent_type: str = "sms_coaching",
    consent_method: str = "sms_double_optin",
    ip_address: str | None = None,
) -> ConsentRecord:
    """Create an active consent record."""
    ph = hash_phone(phone)
    now = datetime.now(timezone.utc)

    # Reactivate if previously revoked
    existing = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.phone_hash == ph,
            ConsentRecord.consent_type == consent_type,
        )
        .first()
    )

    if existing:
        existing.is_active = True
        existing.consented_at = now
        existing.revoked_at = None
        existing.consent_method = consent_method
        existing.ip_address = ip_address
        db.commit()
        db.refresh(existing)
        logger.info("Consent reactivated for phone_hash=%s", ph[:12])
        return existing

    record = ConsentRecord(
        phone_hash=ph,
        consent_type=consent_type,
        consent_method=consent_method,
        is_active=True,
        consented_at=now,
        ip_address=ip_address,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("Consent created for phone_hash=%s", ph[:12])
    return record


def revoke_consent(db: Session, phone: str) -> int:
    """Revoke all active consent records for a phone. Returns count revoked.
    Soft delete only — sets revoked_at, never deletes rows.
    """
    ph = hash_phone(phone)
    now = datetime.now(timezone.utc)
    records = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.phone_hash == ph,
            ConsentRecord.is_active == True,  # noqa: E712
        )
        .all()
    )
    for r in records:
        r.is_active = False
        r.revoked_at = now
    db.commit()
    logger.info("Consent revoked for phone_hash=%s, count=%d", ph[:12], len(records))
    return len(records)
