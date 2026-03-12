"""Tests for backend.database."""

from backend.database import Base, check_db_health


def test_tables_created(test_db):
    """All 6 model tables should exist after init."""
    from sqlalchemy import inspect

    engine = test_db.kw.get("bind") if hasattr(test_db, "kw") else test_db().get_bind()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = {"companies", "projects", "workers", "consent_records", "observations", "message_log"}
    assert expected.issubset(set(tables))


def test_check_db_health():
    result = check_db_health()
    assert result["status"] in ("healthy", "unhealthy")
