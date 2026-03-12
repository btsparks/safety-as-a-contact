"""Tests for backend.config."""

from backend.config import Settings


def test_default_settings():
    s = Settings(database_url="sqlite:///test.db")
    assert s.environment == "development"
    assert s.max_messages_per_phone_per_day == 5
    assert s.sending_window_start == 8
    assert s.sending_window_end == 21


def test_is_sqlite():
    s = Settings(database_url="sqlite:///test.db")
    assert s.is_sqlite is True

    s2 = Settings(database_url="postgresql://user:pass@localhost/db")
    assert s2.is_sqlite is False


def test_is_production():
    s = Settings(environment="production", database_url="sqlite:///test.db")
    assert s.is_production is True

    s2 = Settings(environment="development", database_url="sqlite:///test.db")
    assert s2.is_production is False
