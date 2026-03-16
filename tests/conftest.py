"""Shared test fixtures — in-memory SQLite, FastAPI test client, seed data."""

import os

# Force test config before any imports
os.environ["DATABASE_URL"] = "sqlite:///test_safety.db"
os.environ["ENVIRONMENT"] = "development"
os.environ["PHONE_HASH_SALT"] = "test-salt"
os.environ["TWILIO_ACCOUNT_SID"] = ""
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""  # Force mock mode in tests

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models import Company, ConsentRecord, Observation, Project, Worker, hash_phone, utcnow


@pytest.fixture(autouse=True)
def test_db():
    """Create a fresh in-memory database for each test.

    StaticPool ensures all sessions share the same underlying connection,
    so test fixtures and FastAPI handler see the same data.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(test_db):
    """Yield a database session."""
    session = test_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def seed_company(db):
    """Create a test company."""
    c = Company(name="Test Construction Co")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def seed_project(db, seed_company):
    """Create a test project."""
    p = Project(name="Site Alpha", company_id=seed_company.id, location="Salt Lake City")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def seed_worker(db, seed_company, seed_project):
    """Create a test worker with consent."""
    w = Worker(
        phone_hash=hash_phone("+18015551234"),
        company_id=seed_company.id,
        project_id=seed_project.id,
        trade="concrete",
        experience_level="intermediate",
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


@pytest.fixture
def seed_consent(db):
    """Create an active consent record for the test phone."""
    cr = ConsentRecord(
        phone_hash=hash_phone("+18015551234"),
        consent_type="sms_coaching",
        consent_method="sms_double_optin",
        is_active=True,
        consented_at=utcnow(),
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr


@pytest.fixture
def seed_worker_with_consent(db, seed_company, seed_project):
    """Create a worker AND active consent — ready for coaching tests."""
    w = Worker(
        phone_hash=hash_phone("+18015551234"),
        company_id=seed_company.id,
        project_id=seed_project.id,
        trade="ironworker",
        experience_level="intermediate",
    )
    db.add(w)
    cr = ConsentRecord(
        phone_hash=hash_phone("+18015551234"),
        consent_type="sms_coaching",
        consent_method="sms_double_optin",
        is_active=True,
        consented_at=utcnow(),
    )
    db.add(cr)
    db.commit()
    db.refresh(w)
    db.refresh(cr)
    return w, cr


TEST_PHONE = "+18015551234"
TEST_PHONE_2 = "+18015555678"
