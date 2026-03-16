"""SQLAlchemy models — 10 tables for Phase 3 + Worker Relationship System."""

import hashlib
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.config import settings
from backend.database import Base


def hash_phone(phone: str) -> str:
    """SHA256 hash a phone number with salt. Never store plaintext."""
    return hashlib.sha256(f"{settings.phone_hash_salt}{phone}".encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    projects = relationship("Project", back_populates="company")
    workers = relationship("Worker", back_populates="company")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(200), nullable=False)
    location = Column(String(300))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    company = relationship("Company", back_populates="projects")
    observations = relationship("Observation", back_populates="project")


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True)
    phone_hash = Column(String(64), nullable=False, unique=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"))
    trade = Column(String(50))
    experience_level = Column(String(20), default="entry")  # entry/intermediate/expert
    preferred_language = Column(String(5), default="en")
    created_at = Column(DateTime, default=utcnow)

    company = relationship("Company", back_populates="workers")
    observations = relationship("Observation", back_populates="worker")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True)
    phone_hash = Column(String(64), nullable=False, index=True)
    consent_type = Column(String(50), default="sms_coaching")
    consent_method = Column(String(50))  # sms_double_optin, web_form
    is_active = Column(Boolean, default=True)
    consented_at = Column(DateTime)
    revoked_at = Column(DateTime)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_consent_active", "phone_hash", "consent_type", "is_active"),
    )


class CoachingSession(Base):
    """A multi-turn coaching conversation thread."""
    __tablename__ = "coaching_sessions"

    id = Column(Integer, primary_key=True)
    phone_hash = Column(String(64), nullable=False, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)
    turn_count = Column(Integer, default=0)
    focus_area = Column(String(200))
    coaching_direction = Column(String(200))
    session_sentiment = Column(String(20))  # engaged/uncertain/resistant/curious
    worker_tier = Column(Integer, default=1)  # 1-4
    is_closed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=utcnow)
    last_activity_at = Column(DateTime, default=utcnow)
    ended_at = Column(DateTime)
    response_modes_used = Column(Text)  # JSON list
    hazard_identified = Column(Boolean, default=False)
    hazard_category = Column(String(50))
    teachable_moment = Column(Boolean, default=False)
    toolbox_talk_candidate = Column(Boolean, default=False)
    media_urls = Column(Text)  # JSON list — all photos in this session
    progression_markers = Column(Text)  # JSON assessment data

    observations = relationship("Observation", back_populates="session")


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)  # nullable = anonymous
    project_id = Column(Integer, ForeignKey("projects.id"))
    session_id = Column(Integer, ForeignKey("coaching_sessions.id"), nullable=True)
    raw_text = Column(Text, nullable=False)
    media_urls = Column(Text)  # JSON list of MMS photo URLs
    hazard_category = Column(String(50))
    severity = Column(Integer)  # 1-5
    trade_context = Column(String(50))
    language = Column(String(5), default="en")
    created_at = Column(DateTime, default=utcnow)

    worker = relationship("Worker", back_populates="observations")
    project = relationship("Project", back_populates="observations")
    session = relationship("CoachingSession", back_populates="observations")
    coaching_responses = relationship("CoachingResponse", back_populates="observation")

    __table_args__ = (
        Index("ix_observation_created", "created_at"),
    )


class CoachingResponse(Base):
    __tablename__ = "coaching_responses"

    id = Column(Integer, primary_key=True)
    observation_id = Column(Integer, ForeignKey("observations.id"), nullable=True)
    response_mode = Column(String(20), nullable=False)  # alert/validate/nudge/probe/affirm
    response_text = Column(Text, nullable=False)
    hazard_category = Column(String(50))
    severity = Column(Integer)  # 1-5
    model_used = Column(String(50))
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    observation = relationship("Observation", back_populates="coaching_responses")


class MessageLog(Base):
    __tablename__ = "message_log"

    id = Column(Integer, primary_key=True)
    phone_hash = Column(String(64), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # inbound / outbound
    message_type = Column(String(30))  # observation, consent, opt_out, coaching, system
    twilio_sid = Column(String(50))
    content_preview = Column(String(160))  # first 160 chars only
    status = Column(String(20), default="sent")  # sent, delivered, failed
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_msglog_phone_created", "phone_hash", "created_at"),
    )


class WorkerProfile(Base):
    """Persistent relationship record — the longitudinal view of a worker.

    Keyed on phone_hash so anonymous workers get profiles too.
    Read on every incoming message to inform coaching.
    """
    __tablename__ = "worker_profiles"

    id = Column(Integer, primary_key=True)
    phone_hash = Column(String(64), nullable=False, unique=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=True)

    # Tier
    current_tier = Column(Integer, default=1)
    tier_updated_at = Column(DateTime, default=utcnow)

    # Lifetime counters
    total_sessions = Column(Integer, default=0)
    total_turns = Column(Integer, default=0)

    # Rolling averages
    avg_specificity = Column(Float, default=0.0)
    avg_engagement_depth = Column(Float, default=0.0)
    hazard_accuracy_rate = Column(Float, default=0.0)
    photo_rate = Column(Float, default=0.0)

    # Progression markers
    has_used_trade_vocabulary = Column(Boolean, default=False)
    has_broadened_field_of_view = Column(Boolean, default=False)
    has_shown_ownership_language = Column(Boolean, default=False)
    teachable_moments_count = Column(Integer, default=0)

    # Dominant patterns
    dominant_engagement = Column(String(20), default="low")
    dominant_confidence = Column(String(20), default="uncertain")
    most_common_hazard_category = Column(String(50))

    # AI-generated mentor notes (3-5 sentences)
    mentor_notes = Column(Text)
    mentor_notes_updated_at = Column(DateTime)
    mentor_notes_version = Column(Integer, default=0)

    # Baseline
    baseline_complete = Column(Boolean, default=False)
    baseline_completed_at = Column(DateTime)
    baseline_tier = Column(Integer)

    # Timestamps
    first_interaction_at = Column(DateTime)
    last_interaction_at = Column(DateTime)


class InteractionAssessment(Base):
    """Per-turn raw assessment data — feeds rolling window calculations.

    Every coaching turn saves a row. Can be re-analyzed if the tier
    algorithm changes.
    """
    __tablename__ = "interaction_assessments"

    id = Column(Integer, primary_key=True)
    phone_hash = Column(String(64), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("coaching_sessions.id"), nullable=True)
    observation_id = Column(Integer, ForeignKey("observations.id"), nullable=True)
    coaching_response_id = Column(Integer, ForeignKey("coaching_responses.id"), nullable=True)

    turn_number = Column(Integer, default=1)
    response_mode = Column(String(20))  # alert/validate/nudge/probe/affirm
    hazard_present = Column(Boolean, default=False)
    hazard_category = Column(String(50))
    specificity_score = Column(Integer, default=0)  # 1-5
    worker_engagement = Column(String(20))  # high/medium/low
    worker_confidence = Column(String(20))  # confident/uncertain/resistant
    teachable_moment = Column(Boolean, default=False)
    suggested_next_direction = Column(String(20))  # deeper/broader/close
    has_photo = Column(Boolean, default=False)
    worker_asked_question = Column(Boolean, default=False)
    worker_text_length = Column(Integer, default=0)

    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_ia_phone_created", "phone_hash", "created_at"),
    )
