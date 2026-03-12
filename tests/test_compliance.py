"""Tests for backend.sms.compliance."""

from datetime import datetime, timezone

from backend.models import MessageLog, hash_phone
from backend.sms.compliance import check_rate_limit, is_within_sending_window, validate_outbound_message
from backend.sms.consent import create_consent
from tests.conftest import TEST_PHONE


def test_sending_window_valid_hours():
    for h in range(8, 21):
        assert is_within_sending_window(h) is True, f"Hour {h} should be valid"


def test_sending_window_invalid_hours():
    for h in [0, 1, 5, 7, 21, 22, 23]:
        assert is_within_sending_window(h) is False, f"Hour {h} should be invalid"


def test_sending_window_boundary():
    assert is_within_sending_window(8) is True   # 8am — first valid
    assert is_within_sending_window(20) is True   # 8pm — still valid
    assert is_within_sending_window(21) is False  # 9pm — invalid


def test_rate_limit_under(db):
    assert check_rate_limit(db, TEST_PHONE) is True


def test_rate_limit_at_max(db):
    """After 5 outbound messages, rate limit should block."""
    ph = hash_phone(TEST_PHONE)
    for i in range(5):
        db.add(MessageLog(
            phone_hash=ph,
            direction="outbound",
            message_type="coaching",
            status="sent",
        ))
    db.commit()
    assert check_rate_limit(db, TEST_PHONE) is False


def test_rate_limit_inbound_not_counted(db):
    """Inbound messages don't count against rate limit."""
    ph = hash_phone(TEST_PHONE)
    for i in range(10):
        db.add(MessageLog(
            phone_hash=ph,
            direction="inbound",
            message_type="observation",
            status="received",
        ))
    db.commit()
    assert check_rate_limit(db, TEST_PHONE) is True


def test_validate_outbound_outside_window(db):
    ok, reason = validate_outbound_message(db, TEST_PHONE, hour=7)
    assert ok is False
    assert reason == "outside_sending_window"


def test_validate_outbound_rate_limited(db):
    ph = hash_phone(TEST_PHONE)
    for i in range(5):
        db.add(MessageLog(
            phone_hash=ph, direction="outbound", message_type="coaching", status="sent",
        ))
    db.commit()
    ok, reason = validate_outbound_message(db, TEST_PHONE, hour=12)
    assert ok is False
    assert reason == "rate_limit_exceeded"


def test_validate_outbound_ok(db):
    ok, reason = validate_outbound_message(db, TEST_PHONE, hour=12)
    assert ok is True
    assert reason == "ok"


def test_validate_outbound_skip_rate_limit(db):
    ph = hash_phone(TEST_PHONE)
    for i in range(5):
        db.add(MessageLog(
            phone_hash=ph, direction="outbound", message_type="coaching", status="sent",
        ))
    db.commit()
    ok, reason = validate_outbound_message(db, TEST_PHONE, hour=12, skip_rate_limit=True)
    assert ok is True
