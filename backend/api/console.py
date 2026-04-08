"""Test console API — dev-only endpoints for simulating SMS flows."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import (
    CoachingResponse,
    CoachingSession,
    Company,
    ConsentRecord,
    InteractionAssessment,
    MessageLog,
    Observation,
    Worker,
    WorkerProfile,
    hash_phone,
)
from backend.sms.handler import handle_inbound_message
from backend.test_photo_bank import get_photo_count, get_random_photo

logger = logging.getLogger(__name__)
router = APIRouter()

# Console test company name — created on first simulate with worker context
_TEST_COMPANY_NAME = "Console Test Company"


class SimulateRequest(BaseModel):
    phone: str
    message: str
    image_url: str | None = None
    # Worker context overrides for tuning
    trade: str | None = None
    experience_level: str | None = None
    language: str | None = None
    tier_override: int | None = None  # 1-4, or None for auto


def _dev_only_guard():
    """Return 404 in production (unless demo mode is enabled)."""
    if settings.is_production and not settings.demo_mode:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return None


def _ensure_test_worker(
    db: Session,
    phone: str,
    trade: str | None,
    experience_level: str | None,
    language: str | None,
    tier_override: int | None,
) -> None:
    """Create/update a Worker + WorkerProfile for console testing.

    Only acts when at least one context field is provided.
    """
    if not any([trade, experience_level, language, tier_override]):
        return

    ph = hash_phone(phone)

    # Ensure test company exists
    company = db.query(Company).filter(Company.name == _TEST_COMPANY_NAME).first()
    if not company:
        company = Company(name=_TEST_COMPANY_NAME)
        db.add(company)
        db.commit()
        db.refresh(company)

    # Create or update worker
    worker = db.query(Worker).filter(Worker.phone_hash == ph).first()
    if not worker:
        worker = Worker(
            phone_hash=ph,
            company_id=company.id,
            trade=trade,
            experience_level=experience_level or "entry",
            preferred_language=language or "en",
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)
    else:
        if trade is not None:
            worker.trade = trade
        if experience_level is not None:
            worker.experience_level = experience_level
        if language is not None:
            worker.preferred_language = language
        db.commit()

    # Apply tier override to WorkerProfile
    if tier_override is not None:
        profile = db.query(WorkerProfile).filter(WorkerProfile.phone_hash == ph).first()
        if profile:
            profile.current_tier = tier_override
            db.commit()


def _get_profile_data(db: Session, phone: str) -> dict | None:
    """Fetch worker profile data for the metadata panel."""
    ph = hash_phone(phone)
    profile = db.query(WorkerProfile).filter(WorkerProfile.phone_hash == ph).first()
    if not profile:
        return None

    return {
        "current_tier": profile.current_tier,
        "total_sessions": profile.total_sessions,
        "total_turns": profile.total_turns,
        "avg_specificity": round(profile.avg_specificity or 0, 1),
        "avg_engagement_depth": round(profile.avg_engagement_depth or 0, 1),
        "hazard_accuracy_rate": round((profile.hazard_accuracy_rate or 0) * 100),
        "photo_rate": round((profile.photo_rate or 0) * 100),
        "dominant_engagement": profile.dominant_engagement or "—",
        "dominant_confidence": profile.dominant_confidence or "—",
        "most_common_hazard": profile.most_common_hazard_category or "—",
        "teachable_moments": profile.teachable_moments_count or 0,
        "baseline_complete": profile.baseline_complete or False,
        "baseline_tier": profile.baseline_tier,
        "mentor_notes": profile.mentor_notes or "",
        "mentor_notes_version": profile.mentor_notes_version or 0,
    }


@router.post("/simulate")
def simulate_message(req: SimulateRequest, db: Session = Depends(get_db)):
    """Send a simulated inbound message and get the full handler result."""
    guard = _dev_only_guard()
    if guard:
        return guard

    # Apply worker context overrides before processing
    _ensure_test_worker(
        db, req.phone, req.trade, req.experience_level,
        req.language, req.tier_override,
    )

    # Build media_urls list from optional image_url
    media_urls = [req.image_url] if req.image_url else None

    result = handle_inbound_message(
        db, req.phone, req.message.strip(), media_urls=media_urls,
    )

    response = {
        "action": result.action,
        "response_text": result.response_text,
    }

    if result.coaching_result:
        cr = result.coaching_result
        response["coaching_result"] = {
            "response_mode": cr.response_mode,
            "hazard_category": cr.hazard_category,
            "severity": cr.severity,
            "language": cr.language,
            "model_used": cr.model_used,
            "prompt_tokens": cr.prompt_tokens,
            "completion_tokens": cr.completion_tokens,
            "latency_ms": cr.latency_ms,
            "is_mock": cr.is_mock,
            "has_photo": cr.has_photo,
            "turn_number": cr.turn_number,
            "session_id": cr.session_id,
            # Assessment metadata
            "specificity_score": cr.specificity_score,
            "worker_engagement": cr.worker_engagement,
            "worker_confidence": cr.worker_confidence,
            "teachable_moment": cr.teachable_moment,
            "suggested_next_direction": cr.suggested_next_direction,
        }

    # Attach worker profile data
    response["worker_profile"] = _get_profile_data(db, req.phone)

    return JSONResponse(content=response)


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    """List all phone hashes with message counts."""
    guard = _dev_only_guard()
    if guard:
        return guard

    rows = (
        db.query(
            MessageLog.phone_hash,
            func.count(MessageLog.id).label("message_count"),
            func.max(MessageLog.created_at).label("last_message"),
        )
        .group_by(MessageLog.phone_hash)
        .order_by(func.max(MessageLog.created_at).desc())
        .all()
    )

    conversations = [
        {
            "phone_hash": r.phone_hash[:12] + "...",
            "phone_hash_full": r.phone_hash,
            "message_count": r.message_count,
            "last_message": r.last_message.isoformat() if r.last_message else None,
        }
        for r in rows
    ]

    return JSONResponse(content={"conversations": conversations})


@router.get("/conversation/{phone}")
def get_conversation(phone: str, db: Session = Depends(get_db)):
    """Get full message history + coaching metadata for a phone number."""
    guard = _dev_only_guard()
    if guard:
        return guard

    ph = hash_phone(phone)
    messages = (
        db.query(MessageLog)
        .filter(MessageLog.phone_hash == ph)
        .order_by(MessageLog.created_at.asc())
        .all()
    )

    # Get coaching responses linked to observations from this phone
    observations = (
        db.query(Observation)
        .join(MessageLog, MessageLog.phone_hash == ph)
        .filter(MessageLog.message_type == "observation", MessageLog.direction == "inbound")
        .all()
    )
    obs_ids = [o.id for o in observations]
    coaching_responses = (
        db.query(CoachingResponse)
        .filter(CoachingResponse.observation_id.in_(obs_ids))
        .all()
    ) if obs_ids else []

    coaching_by_obs = {cr.observation_id: cr for cr in coaching_responses}

    result_messages = []
    for msg in messages:
        entry = {
            "id": msg.id,
            "direction": msg.direction,
            "message_type": msg.message_type,
            "content_preview": msg.content_preview,
            "status": msg.status,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }
        result_messages.append(entry)

    result_coaching = []
    for cr in coaching_responses:
        result_coaching.append({
            "observation_id": cr.observation_id,
            "response_mode": cr.response_mode,
            "hazard_category": cr.hazard_category,
            "severity": cr.severity,
            "model_used": cr.model_used,
            "latency_ms": cr.latency_ms,
        })

    return JSONResponse(content={
        "phone_hash": ph[:12] + "...",
        "messages": result_messages,
        "coaching_responses": result_coaching,
    })


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get mode distribution, latency stats, compliance blocks."""
    guard = _dev_only_guard()
    if guard:
        return guard

    # Mode distribution
    mode_rows = (
        db.query(
            CoachingResponse.response_mode,
            func.count(CoachingResponse.id).label("count"),
        )
        .group_by(CoachingResponse.response_mode)
        .all()
    )
    mode_distribution = {r.response_mode: r.count for r in mode_rows}

    # Latency stats
    latency_row = db.query(
        func.avg(CoachingResponse.latency_ms).label("avg"),
        func.max(CoachingResponse.latency_ms).label("max"),
        func.min(CoachingResponse.latency_ms).label("min"),
    ).first()

    avg_latency = round(latency_row.avg, 1) if latency_row.avg else 0
    max_latency = latency_row.max or 0
    min_latency = latency_row.min or 0

    # Totals
    total_messages = db.query(func.count(MessageLog.id)).scalar() or 0
    total_observations = db.query(func.count(Observation.id)).scalar() or 0
    total_coaching = db.query(func.count(CoachingResponse.id)).scalar() or 0

    # Compliance blocks (messages with status=blocked)
    blocked = (
        db.query(func.count(MessageLog.id))
        .filter(MessageLog.status == "blocked")
        .scalar() or 0
    )

    return JSONResponse(content={
        "mode_distribution": mode_distribution,
        "avg_latency_ms": avg_latency,
        "max_latency_ms": max_latency,
        "min_latency_ms": min_latency,
        "total_messages": total_messages,
        "total_observations": total_observations,
        "total_coaching_responses": total_coaching,
        "compliance_blocks": blocked,
    })


@router.get("/random-photo")
def random_photo(trade: str | None = None):
    """Get a random analyzed photo from the training catalog."""
    guard = _dev_only_guard()
    if guard:
        return guard

    photo = get_random_photo(trade or None)
    if not photo:
        return JSONResponse(
            status_code=404,
            content={"error": "No analyzed photos found in training DB"},
        )

    return JSONResponse(content={
        "id": photo["id"],
        "url": f"/api/training/photo-image/{photo['id']}",
        "scenario": photo["scenario"][:200],
        "hazard_hint": photo["hazard_hint"][:200] if photo["hazard_hint"] else "",
        "trade": photo["trade"] or "general",
        "severity": photo["severity"],
        "recommended_mode": photo["recommended_mode"],
        "bank_size": get_photo_count(),
    })


@router.get("/profile/{phone}")
def get_worker_profile(phone: str, db: Session = Depends(get_db)):
    """Get worker profile + recent assessments for a phone number."""
    guard = _dev_only_guard()
    if guard:
        return guard

    profile_data = _get_profile_data(db, phone)

    # Get worker context (trade, experience, language)
    ph = hash_phone(phone)
    worker = db.query(Worker).filter(Worker.phone_hash == ph).first()
    worker_context = None
    if worker:
        worker_context = {
            "trade": worker.trade or "",
            "experience_level": worker.experience_level or "entry",
            "language": worker.preferred_language or "en",
        }

    # Get recent assessments
    assessments = (
        db.query(InteractionAssessment)
        .filter(InteractionAssessment.phone_hash == ph)
        .order_by(InteractionAssessment.created_at.desc())
        .limit(10)
        .all()
    )
    assessment_list = [
        {
            "turn_number": a.turn_number,
            "response_mode": a.response_mode,
            "hazard_present": a.hazard_present,
            "specificity_score": a.specificity_score,
            "worker_engagement": a.worker_engagement,
            "worker_confidence": a.worker_confidence,
            "teachable_moment": a.teachable_moment,
            "has_photo": a.has_photo,
        }
        for a in assessments
    ]

    return JSONResponse(content={
        "profile": profile_data,
        "worker_context": worker_context,
        "recent_assessments": assessment_list,
    })


@router.delete("/reset")
def reset_test_data(db: Session = Depends(get_db)):
    """Clear all test data for clean runs. Dev-only."""
    guard = _dev_only_guard()
    if guard:
        return guard

    counts = {
        "interaction_assessments": db.query(InteractionAssessment).delete(),
        "coaching_responses": db.query(CoachingResponse).delete(),
        "observations": db.query(Observation).delete(),
        "coaching_sessions": db.query(CoachingSession).delete(),
        "message_log": db.query(MessageLog).delete(),
        "consent_records": db.query(ConsentRecord).delete(),
        "worker_profiles": db.query(WorkerProfile).delete(),
        "workers": db.query(Worker).delete(),
    }
    db.commit()

    return JSONResponse(content={"deleted": counts})
