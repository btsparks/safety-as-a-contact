"""Tests for backend.models."""

from backend.models import (
    Company,
    ConsentRecord,
    MessageLog,
    Observation,
    Project,
    Worker,
    hash_phone,
    utcnow,
)


def test_hash_phone_deterministic():
    assert hash_phone("+18015551234") == hash_phone("+18015551234")


def test_hash_phone_different_numbers():
    assert hash_phone("+18015551234") != hash_phone("+18015555678")


def test_hash_phone_length():
    h = hash_phone("+18015551234")
    assert len(h) == 64  # SHA256 hex digest


def test_create_company(db):
    c = Company(name="Acme Construction")
    db.add(c)
    db.commit()
    assert c.id is not None
    assert c.name == "Acme Construction"
    assert c.created_at is not None


def test_create_project_with_company(db, seed_company):
    p = Project(name="Highway Bridge", company_id=seed_company.id)
    db.add(p)
    db.commit()
    assert p.company_id == seed_company.id
    assert p.active is True


def test_create_worker(db, seed_company):
    w = Worker(
        phone_hash=hash_phone("+18015559999"),
        company_id=seed_company.id,
        trade="electrical",
        experience_level="expert",
        preferred_language="es",
    )
    db.add(w)
    db.commit()
    assert w.preferred_language == "es"
    assert w.experience_level == "expert"


def test_observation_nullable_worker(db, seed_project):
    """Anonymous observations — worker_id must be nullable."""
    o = Observation(
        worker_id=None,
        project_id=seed_project.id,
        raw_text="Exposed rebar near entrance",
        hazard_category="environmental",
        severity=3,
    )
    db.add(o)
    db.commit()
    assert o.id is not None
    assert o.worker_id is None


def test_consent_record(db):
    cr = ConsentRecord(
        phone_hash=hash_phone("+18015551234"),
        consent_type="sms_coaching",
        consent_method="sms_double_optin",
        is_active=True,
        consented_at=utcnow(),
    )
    db.add(cr)
    db.commit()
    assert cr.is_active is True
    assert cr.revoked_at is None


def test_message_log(db):
    ml = MessageLog(
        phone_hash=hash_phone("+18015551234"),
        direction="inbound",
        message_type="observation",
        content_preview="Saw a trip hazard near the south gate",
        status="received",
    )
    db.add(ml)
    db.commit()
    assert ml.direction == "inbound"
