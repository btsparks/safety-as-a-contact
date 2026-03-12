"""Tests for backend.sms.sender."""

from backend.models import MessageLog, hash_phone
from backend.sms.consent import create_consent
from backend.sms.sender import send_sms
from tests.conftest import TEST_PHONE, TEST_PHONE_2


def test_send_without_consent_blocked(db):
    """Should block sending when no consent exists."""
    result = send_sms(db, TEST_PHONE, "Hello", hour=12)
    assert result["status"] == "blocked"
    assert result["reason"] == "no_consent"


def test_send_with_consent_outside_window(db):
    """Should block sending outside 8am-9pm."""
    create_consent(db, TEST_PHONE)
    result = send_sms(db, TEST_PHONE, "Hello", hour=7)
    assert result["status"] == "blocked"
    assert result["reason"] == "outside_sending_window"


def test_send_with_consent_ok(db):
    """Should send (dev mode = logged) when consent + window ok."""
    create_consent(db, TEST_PHONE)
    result = send_sms(db, TEST_PHONE, "Good catch on that hazard!", hour=12)
    assert result["status"] == "sent"

    # Should be logged in message_log
    log = db.query(MessageLog).filter(
        MessageLog.phone_hash == hash_phone(TEST_PHONE),
        MessageLog.direction == "outbound",
    ).first()
    assert log is not None
    assert log.status == "sent"


def test_send_skip_compliance(db):
    """skip_compliance=True should bypass consent and window checks."""
    result = send_sms(db, TEST_PHONE_2, "Opt-out confirmed", skip_compliance=True, hour=3)
    assert result["status"] == "sent"


def test_send_rate_limited(db):
    """Should block after 5 messages in a day."""
    create_consent(db, TEST_PHONE)
    for i in range(5):
        send_sms(db, TEST_PHONE, f"Message {i+1}", hour=12)

    result = send_sms(db, TEST_PHONE, "Message 6", hour=12)
    assert result["status"] == "blocked"
    assert result["reason"] == "rate_limit_exceeded"


def test_send_logs_content_preview(db):
    """Content preview should be truncated to 160 chars."""
    create_consent(db, TEST_PHONE)
    long_msg = "A" * 300
    send_sms(db, TEST_PHONE, long_msg, hour=12)

    log = db.query(MessageLog).filter(
        MessageLog.phone_hash == hash_phone(TEST_PHONE),
        MessageLog.direction == "outbound",
    ).first()
    assert len(log.content_preview) == 160
