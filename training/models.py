"""Training harness models — 5 tables in training.db."""

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

from training.db import TrainingBase


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PhotoCatalog(TrainingBase):
    """Every photo in the dataset, with extracted metadata."""
    __tablename__ = "photo_catalog"

    id = Column(Integer, primary_key=True)
    file_path = Column(String(500), nullable=False, unique=True)
    file_name = Column(String(300), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(Integer)
    date_taken = Column(DateTime, nullable=True)
    photographer = Column(String(100), nullable=True)
    project_name = Column(String(200), nullable=True)
    project_number = Column(String(20), nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lon = Column(Float, nullable=True)
    has_gps = Column(Boolean, default=False)
    is_pdf = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    scene_analyses = relationship("SceneAnalysis", back_populates="photo")
    benchmark_results = relationship("BenchmarkResult", back_populates="photo")


class SceneAnalysis(TrainingBase):
    """Claude Vision analysis of a photo — the ground truth for benchmarking."""
    __tablename__ = "scene_analysis"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, ForeignKey("photo_catalog.id"), nullable=False, index=True)
    scene_description = Column(Text)
    hazards_found = Column(Text)  # JSON list
    trade_context = Column(String(100))
    severity = Column(Integer)  # 1-5
    recommended_mode = Column(String(20))
    coaching_focus = Column(Text)
    scene_tags = Column(Text)  # JSON list
    raw_response = Column(Text)
    model_used = Column(String(50))
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    photo = relationship("PhotoCatalog", back_populates="scene_analyses")


class PromptVersion(TrainingBase):
    """Captures the full rendered system prompt for reproducibility."""
    __tablename__ = "prompt_version"

    id = Column(Integer, primary_key=True)
    version_label = Column(String(100), nullable=False)
    system_prompt_text = Column(Text, nullable=False)
    prompt_params = Column(Text)  # JSON of kwargs
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    benchmark_runs = relationship("BenchmarkRun", back_populates="prompt_version")


class BenchmarkRun(TrainingBase):
    """One complete evaluation pass over a set of photos."""
    __tablename__ = "benchmark_run"

    id = Column(Integer, primary_key=True)
    prompt_version_id = Column(Integer, ForeignKey("prompt_version.id"), nullable=False)
    run_label = Column(String(200))
    model_used = Column(String(50))
    trade = Column(String(50), nullable=True)
    experience_level = Column(String(20), default="entry")
    worker_tier = Column(Integer, default=1)
    photo_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    prompt_version = relationship("PromptVersion", back_populates="benchmark_runs")
    results = relationship("BenchmarkResult", back_populates="run")


class BenchmarkResult(TrainingBase):
    """One coaching response for one photo in a benchmark run."""
    __tablename__ = "benchmark_result"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("benchmark_run.id"), nullable=False, index=True)
    photo_id = Column(Integer, ForeignKey("photo_catalog.id"), nullable=False)
    scene_analysis_id = Column(Integer, ForeignKey("scene_analysis.id"), nullable=True)

    # Coaching response
    response_text = Column(Text, nullable=False)
    response_mode = Column(String(20))
    hazard_category = Column(String(50))
    severity = Column(Integer)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)

    # Auto-scores
    score_length_ok = Column(Boolean)
    score_has_question = Column(Boolean)
    score_is_specific = Column(Boolean)
    score_no_prohibited = Column(Boolean)
    score_mode_match = Column(Boolean, nullable=True)
    auto_score_total = Column(Integer, default=0)

    # Human review
    human_rating = Column(Integer, nullable=True)
    human_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    run = relationship("BenchmarkRun", back_populates="results")
    photo = relationship("PhotoCatalog", back_populates="benchmark_results")

    __table_args__ = (
        Index("ix_br_run_photo", "run_id", "photo_id"),
    )
