"""Training review API — browse analyzed photos, run live conversations, rate responses.

All conversations go through the real coaching engine with sessions, profiles,
and thread history. This is NOT a mock — it exercises the full pipeline.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from backend.coaching.engine import run_coaching
from backend.coaching.profile import get_or_create_profile
from backend.config import settings
from backend.database import get_db
from backend.models import (
    CoachingResponse,
    CoachingSession,
    InteractionAssessment,
    Observation,
    WorkerProfile,
    hash_phone,
    utcnow,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Training uses a fixed phone prefix so conversations don't collide with SMS console
TRAINING_PHONE_PREFIX = "+19995550"  # +19995550001, +19995550002, etc.


# ---- Models ----

class ConversationRequest(BaseModel):
    photo_id: int
    message: str = ""


class RatingRequest(BaseModel):
    benchmark_result_id: int
    rating: int  # 1-5
    notes: str = ""


# ---- Helpers ----

def _phone_for_photo(photo_id: int) -> str:
    """Deterministic phone number per photo for training conversations."""
    return f"{TRAINING_PHONE_PREFIX}{photo_id:04d}"


def _get_training_db():
    """Get training database session."""
    from training.db import TrainingSession, init_training_db
    init_training_db()
    return TrainingSession()


# ---- Endpoints ----

@router.get("/photos")
def list_analyzed_photos():
    """List all photos that have scene analyses, with their analysis data."""
    tdb = _get_training_db()

    from training.models import PhotoCatalog, SceneAnalysis

    rows = (
        tdb.query(PhotoCatalog, SceneAnalysis)
        .join(SceneAnalysis, SceneAnalysis.photo_id == PhotoCatalog.id)
        .filter(PhotoCatalog.is_pdf == False)
        .order_by(PhotoCatalog.date_taken.asc())
        .all()
    )

    photos = []
    for photo, scene in rows:
        hazards = []
        try:
            hazards = json.loads(scene.hazards_found or "[]")
        except json.JSONDecodeError:
            pass

        tags = []
        try:
            tags = json.loads(scene.scene_tags or "[]")
        except json.JSONDecodeError:
            pass

        photos.append({
            "id": photo.id,
            "file_name": photo.file_name,
            "date_taken": photo.date_taken.isoformat() if photo.date_taken else None,
            "photographer": photo.photographer,
            "project_name": photo.project_name,
            "has_gps": photo.has_gps,
            "scene": {
                "id": scene.id,
                "description": scene.scene_description,
                "hazards": hazards,
                "trade_context": scene.trade_context,
                "severity": scene.severity,
                "recommended_mode": scene.recommended_mode,
                "coaching_focus": scene.coaching_focus,
                "tags": tags,
            },
        })

    tdb.close()
    return JSONResponse(content={"photos": photos, "total": len(photos)})


@router.get("/photo-image/{photo_id}")
def serve_photo(photo_id: int):
    """Serve a photo file by its catalog ID."""
    tdb = _get_training_db()
    from training.models import PhotoCatalog

    photo = tdb.query(PhotoCatalog).get(photo_id)
    tdb.close()

    if not photo:
        return JSONResponse(status_code=404, content={"error": "Photo not found"})

    path = Path(photo.file_path)
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "File not found on disk"})

    return FileResponse(path, media_type="image/jpeg")


@router.post("/converse")
def converse(req: ConversationRequest, db: DBSession = Depends(get_db)):
    """Send a message as a worker for a specific photo. Goes through the REAL
    coaching engine with session tracking and worker profiles.

    First call for a photo starts a new conversation. Subsequent calls continue it.
    The photo is always included as context (simulating MMS).
    """
    phone = _phone_for_photo(req.photo_id)
    ph = hash_phone(phone)

    # Get photo path for reference
    tdb = _get_training_db()
    from training.models import PhotoCatalog, SceneAnalysis

    photo = tdb.query(PhotoCatalog).get(req.photo_id)
    scene = (
        tdb.query(SceneAnalysis)
        .filter(SceneAnalysis.photo_id == req.photo_id)
        .first()
    )
    tdb.close()

    if not photo:
        return JSONResponse(status_code=404, content={"error": "Photo not found"})

    # Build message text
    message_text = req.message.strip() if req.message else "(photo only)"

    # Create observation record
    obs = Observation(raw_text=message_text)
    db.add(obs)
    db.commit()
    db.refresh(obs)

    # Get trade context from scene analysis if available
    trade = None
    if scene and scene.trade_context:
        # Map broad trade descriptions to our trade keys
        tc = scene.trade_context.lower()
        if "pipe" in tc or "plumb" in tc:
            trade = "plumbing"
        elif "electri" in tc:
            trade = "electrical"
        elif "concrete" in tc:
            trade = "concrete"
        elif "steel" in tc or "iron" in tc:
            trade = "steel_fabrication"
        elif "crane" in tc or "heavy equip" in tc:
            trade = "heavy_equipment"
        elif "weld" in tc:
            trade = "welding"

    # Run through the real coaching engine
    # Note: We pass media_urls=None for local training since the photos are
    # local files, not accessible via URL for the Claude API. The photo context
    # comes from the scene analysis + worker's text description instead.
    result = run_coaching(
        db=db,
        observation_text=message_text,
        trade=trade,
        experience_level="intermediate",
        observation_id=obs.id,
        phone_hash=ph,
    )

    # Get the profile for this worker
    profile = get_or_create_profile(db, ph)

    # Get thread history for display
    session = None
    thread = []
    if result.session_id:
        session = db.get(CoachingSession, result.session_id)
        # Get all observations + responses in this session
        session_obs = (
            db.query(Observation)
            .filter(Observation.session_id == result.session_id)
            .order_by(Observation.created_at.asc())
            .all()
        )
        for o in session_obs:
            thread.append({
                "role": "worker",
                "text": o.raw_text,
                "time": o.created_at.isoformat() if o.created_at else None,
            })
            for cr in o.coaching_responses:
                thread.append({
                    "role": "coach",
                    "text": cr.response_text,
                    "mode": cr.response_mode,
                    "time": cr.created_at.isoformat() if cr.created_at else None,
                })
                break

    response = {
        "response_text": result.response_text,
        "response_mode": result.response_mode,
        "hazard_category": result.hazard_category,
        "severity": result.severity,
        "language": result.language,
        "model_used": result.model_used,
        "is_mock": result.is_mock,
        "turn_number": result.turn_number,
        "session_id": result.session_id,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "latency_ms": result.latency_ms,
        "specificity_score": result.specificity_score,
        "worker_engagement": result.worker_engagement,
        "worker_confidence": result.worker_confidence,
        "teachable_moment": result.teachable_moment,
        "suggested_next_direction": result.suggested_next_direction,
        "profile": {
            "current_tier": profile.current_tier,
            "total_sessions": profile.total_sessions,
            "total_turns": profile.total_turns,
            "avg_specificity": round(profile.avg_specificity, 1),
            "hazard_accuracy_rate": round(profile.hazard_accuracy_rate * 100),
            "baseline_complete": profile.baseline_complete,
            "mentor_notes": profile.mentor_notes,
            "dominant_engagement": profile.dominant_engagement,
            "dominant_confidence": profile.dominant_confidence,
        },
        "thread": thread,
    }

    return JSONResponse(content=response)


@router.post("/reset-conversation/{photo_id}")
def reset_conversation(photo_id: int, db: DBSession = Depends(get_db)):
    """Reset the conversation for a specific photo (close session, clear data)."""
    phone = _phone_for_photo(photo_id)
    ph = hash_phone(phone)

    # Close all sessions for this phone
    sessions = (
        db.query(CoachingSession)
        .filter(CoachingSession.phone_hash == ph)
        .all()
    )
    for s in sessions:
        s.is_closed = True
        s.ended_at = utcnow()

    # Delete interaction assessments
    db.query(InteractionAssessment).filter(
        InteractionAssessment.phone_hash == ph
    ).delete()

    # Delete worker profile
    db.query(WorkerProfile).filter(WorkerProfile.phone_hash == ph).delete()

    db.commit()

    return JSONResponse(content={"status": "ok", "sessions_closed": len(sessions)})


@router.post("/rate")
def rate_response(req: RatingRequest):
    """Save a human rating for a benchmark result."""
    tdb = _get_training_db()
    from training.models import BenchmarkResult

    result = tdb.query(BenchmarkResult).get(req.benchmark_result_id)
    if not result:
        tdb.close()
        return JSONResponse(status_code=404, content={"error": "Result not found"})

    result.human_rating = req.rating
    result.human_notes = req.notes
    result.reviewed_at = utcnow()
    tdb.commit()
    tdb.close()

    return JSONResponse(content={"status": "ok"})


@router.get("/benchmark-response/{photo_id}")
def get_benchmark_response(photo_id: int):
    """Get the most recent benchmark response for a photo."""
    tdb = _get_training_db()
    from training.models import BenchmarkResult

    result = (
        tdb.query(BenchmarkResult)
        .filter(BenchmarkResult.photo_id == photo_id)
        .order_by(BenchmarkResult.id.desc())
        .first()
    )

    if not result:
        tdb.close()
        return JSONResponse(content={"benchmark": None})

    data = {
        "id": result.id,
        "response_text": result.response_text,
        "response_mode": result.response_mode,
        "hazard_category": result.hazard_category,
        "severity": result.severity,
        "auto_scores": {
            "length_ok": result.score_length_ok,
            "has_question": result.score_has_question,
            "is_specific": result.score_is_specific,
            "no_prohibited": result.score_no_prohibited,
            "mode_match": result.score_mode_match,
            "total": result.auto_score_total,
        },
        "human_rating": result.human_rating,
        "human_notes": result.human_notes,
    }
    tdb.close()
    return JSONResponse(content={"benchmark": data})
