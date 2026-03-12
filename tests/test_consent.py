"""Tests for backend.sms.consent."""

from backend.sms.consent import (
    create_consent,
    is_opt_in,
    is_opt_out,
    revoke_consent,
    verify_consent,
)
from tests.conftest import TEST_PHONE, TEST_PHONE_2


def test_is_opt_out_keywords():
    for kw in ["STOP", "stop", "Cancel", "END", "quit", "UNSUBSCRIBE", "Stopall"]:
        assert is_opt_out(kw), f"{kw} should be opt-out"
    assert not is_opt_out("hello")
    assert not is_opt_out("yes")


def test_is_opt_in_keywords():
    for kw in ["YES", "yes", "Yep", "ok", "confirm", "START", "start"]:
        assert is_opt_in(kw), f"{kw} should be opt-in"
    assert not is_opt_in("hello")
    assert not is_opt_in("STOP")


def test_verify_consent_no_record(db):
    assert verify_consent(db, TEST_PHONE) is False


def test_create_and_verify_consent(db):
    create_consent(db, TEST_PHONE)
    assert verify_consent(db, TEST_PHONE) is True


def test_revoke_consent(db):
    create_consent(db, TEST_PHONE)
    assert verify_consent(db, TEST_PHONE) is True

    count = revoke_consent(db, TEST_PHONE)
    assert count == 1
    assert verify_consent(db, TEST_PHONE) is False


def test_revoke_no_consent(db):
    count = revoke_consent(db, TEST_PHONE_2)
    assert count == 0


def test_reactivate_consent(db):
    create_consent(db, TEST_PHONE)
    revoke_consent(db, TEST_PHONE)
    assert verify_consent(db, TEST_PHONE) is False

    create_consent(db, TEST_PHONE)
    assert verify_consent(db, TEST_PHONE) is True


def test_consent_different_phones(db):
    create_consent(db, TEST_PHONE)
    assert verify_consent(db, TEST_PHONE) is True
    assert verify_consent(db, TEST_PHONE_2) is False
