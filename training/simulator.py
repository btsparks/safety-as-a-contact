"""Simulation engine — orchestrates multi-session longitudinal coaching simulations.

Runs a persona through N coaching sessions, each with M turns, using real photos
from the training bank and the real coaching engine. Produces a SimulationReport
with tier progression, transcripts, mentor notes history, and profile snapshots.

Enhanced with evaluator integration for the headless quality pipeline.
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from backend.coaching.engine import run_coaching
from backend.coaching.profile import get_or_create_profile
from backend.models import (
    CoachingSession,
    Observation,
    WorkerProfile,
    hash_phone,
    utcnow,
)
from training.personas import Persona

logger = logging.getLogger(__name__)


@dataclass
class SessionTranscript:
    """Transcript of a single coaching session."""

    session_number: int
    turns: list[dict] = field(default_factory=list)
    tier_at_start: int = 1
    tier_at_end: int = 1
    photo_id: int | None = None
    mentor_notes: str = ""


@dataclass
class SimulationReport:
    """Complete report from a longitudinal simulation run."""

    persona_key: str
    persona_name: str
    num_sessions: int
    turns_per_session: int
    tier_progression: list[int] = field(default_factory=list)
    sessions: list[SessionTranscript] = field(default_factory=list)
    mentor_notes_history: list[str] = field(default_factory=list)
    final_profile: dict = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Serialize for JSON API response."""
        return {
            "persona_key": self.persona_key,
            "persona_name": self.persona_name,
            "num_sessions": self.num_sessions,
            "turns_per_session": self.turns_per_session,
            "tier_progression": self.tier_progression,
            "sessions": [
                {
                    "session_number": s.session_number,
                    "turns": s.turns,
                    "tier_at_start": s.tier_at_start,
                    "tier_at_end": s.tier_at_end,
                    "photo_id": s.photo_id,
                    "mentor_notes": s.mentor_notes,
                }
                for s in self.sessions
            ],
            "mentor_notes_history": self.mentor_notes_history,
            "final_profile": self.final_profile,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }


def _get_random_photo_ids(count: int) -> list[int]:
    """Get random photo IDs from the training catalog."""
    try:
        from training.db import TrainingSession, init_training_db
        from training.models import PhotoCatalog, SceneAnalysis

        init_training_db()
        tdb = TrainingSession()
        # Get photos that have scene analyses (analyzed)
        photo_ids = [
            row[0]
            for row in tdb.query(PhotoCatalog.id)
            .join(SceneAnalysis, SceneAnalysis.photo_id == PhotoCatalog.id)
            .filter(PhotoCatalog.is_pdf == False)
            .all()
        ]
        tdb.close()

        if not photo_ids:
            return []

        return random.sample(photo_ids, min(count, len(photo_ids)))
    except Exception as e:
        logger.warning("Could not fetch training photos: %s", e)
        return []


def _get_photo_url(photo_id: int) -> str:
    """Build the local API URL for a training photo."""
    return f"/api/training/photo-image/{photo_id}"


def _close_active_sessions(db: DBSession, phone_hash: str) -> None:
    """Close all active sessions for a phone hash (between simulation sessions)."""
    now = utcnow()
    sessions = (
        db.query(CoachingSession)
        .filter(
            CoachingSession.phone_hash == phone_hash,
            CoachingSession.is_closed == False,
        )
        .all()
    )
    for s in sessions:
        s.is_closed = True
        s.ended_at = now
    db.commit()


def run_simulation(
    db: DBSession,
    persona: Persona,
    num_sessions: int = 10,
    turns_per_session: int = 4,
) -> SimulationReport:
    """Run a full longitudinal simulation for a persona.

    Each session:
    1. Optionally pick a random photo from the training bank
    2. Worker AI generates initial message (with optional chaos)
    3. Feed through real run_coaching()
    4. Worker AI responds
    5. Repeat for N turns
    6. Close session
    7. Record tier, mentor notes, transcript
    """
    from training.worker_ai import generate_worker_message

    phone_hash = hash_phone(persona.phone)
    photo_ids = _get_random_photo_ids(num_sessions)

    report = SimulationReport(
        persona_key=persona.name.lower(),
        persona_name=persona.name,
        num_sessions=num_sessions,
        turns_per_session=turns_per_session,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    start_time = time.monotonic()

    for session_num in range(1, num_sessions + 1):
        logger.info(
            "Simulation %s: session %d/%d",
            persona.name,
            session_num,
            num_sessions,
        )

        # Close previous sessions to force a new one
        _close_active_sessions(db, phone_hash)

        # Get starting tier
        profile = get_or_create_profile(db, phone_hash)
        tier_at_start = profile.current_tier

        # Decide if this session has a photo
        has_photo = random.random() < persona.photo_frequency
        photo_id = None
        media_urls = None
        if has_photo and photo_ids:
            photo_id = photo_ids[(session_num - 1) % len(photo_ids)]
            media_urls = [_get_photo_url(photo_id)]

        transcript = SessionTranscript(
            session_number=session_num,
            tier_at_start=tier_at_start,
            photo_id=photo_id,
        )

        coach_message = None

        for turn in range(1, turns_per_session + 1):
            # Worker generates a message (with possible chaos)
            worker_text, chaos_mode = generate_worker_message(
                persona=persona,
                session_number=session_num,
                turn_number=turn,
                has_photo=(has_photo and turn == 1),
                coach_message=coach_message,
            )

            transcript.turns.append({
                "turn": turn,
                "role": "worker",
                "text": worker_text,
                "has_photo": has_photo and turn == 1,
                "chaos_mode": chaos_mode,
            })

            # Create observation record
            obs = Observation(raw_text=worker_text)
            db.add(obs)
            db.commit()
            db.refresh(obs)

            # Run through real coaching engine
            result = run_coaching(
                db=db,
                observation_text=worker_text,
                trade=persona.trade,
                experience_level=persona.experience_level,
                observation_id=obs.id,
                media_urls=media_urls if turn == 1 else None,
                phone_hash=phone_hash,
                preferred_language=persona.language,
            )

            transcript.turns.append({
                "turn": turn,
                "role": "coach",
                "text": result.response_text,
                "mode": result.response_mode,
                "specificity": result.specificity_score,
                "engagement": result.worker_engagement,
            })

            coach_message = result.response_text

        # Session complete — record tier
        profile = get_or_create_profile(db, phone_hash)
        transcript.tier_at_end = profile.current_tier
        transcript.mentor_notes = profile.mentor_notes or ""

        report.tier_progression.append(profile.current_tier)
        report.mentor_notes_history.append(profile.mentor_notes or "")
        report.sessions.append(transcript)

    # Final profile snapshot
    profile = get_or_create_profile(db, phone_hash)
    report.final_profile = {
        "current_tier": profile.current_tier,
        "total_sessions": profile.total_sessions,
        "total_turns": profile.total_turns,
        "avg_specificity": round(profile.avg_specificity, 1),
        "hazard_accuracy_rate": round(profile.hazard_accuracy_rate * 100),
        "baseline_complete": profile.baseline_complete,
        "mentor_notes": profile.mentor_notes,
        "dominant_engagement": profile.dominant_engagement,
        "dominant_confidence": profile.dominant_confidence,
    }

    report.finished_at = datetime.now(timezone.utc).isoformat()
    report.elapsed_seconds = time.monotonic() - start_time

    return report
