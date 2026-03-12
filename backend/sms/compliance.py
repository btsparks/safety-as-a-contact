"""SMS compliance checks — sending window, rate limiting."""

import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import MessageLog, hash_phone

logger = logging.getLogger(__name__)


def is_within_sending_window(hour: int | None = None) -> bool:
    """Check if current hour is within 8am-9pm sending window.

    Args:
        hour: Override hour for testing. If None, uses current UTC hour.
              In production, this should be the recipient's local hour.
    """
    if hour is None:
        hour = datetime.now(timezone.utc).hour
    return settings.sending_window_start <= hour < settings.sending_window_end


def check_rate_limit(db: Session, phone: str, today: date | None = None) -> bool:
    """Check if phone is under the daily message limit.

    Returns True if more messages can be sent.
    """
    ph = hash_phone(phone)
    if today is None:
        today = datetime.now(timezone.utc).date()

    count = (
        db.query(MessageLog)
        .filter(
            MessageLog.phone_hash == ph,
            MessageLog.direction == "outbound",
            MessageLog.created_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc),
            MessageLog.status.in_(["sent", "delivered"]),
        )
        .count()
    )
    within_limit = count < settings.max_messages_per_phone_per_day
    if not within_limit:
        logger.warning("Rate limit reached for phone_hash=%s, count=%d", ph[:12], count)
    return within_limit


def validate_outbound_message(
    db: Session, phone: str, hour: int | None = None, skip_rate_limit: bool = False
) -> tuple[bool, str]:
    """Run all compliance checks before sending a message.

    Returns (ok, reason). If ok is False, do NOT send.
    skip_rate_limit: True for opt-out confirmations.
    """
    if not is_within_sending_window(hour):
        return False, "outside_sending_window"

    if not skip_rate_limit and not check_rate_limit(db, phone):
        return False, "rate_limit_exceeded"

    return True, "ok"
