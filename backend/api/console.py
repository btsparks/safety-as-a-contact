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
    ConsentRecord,
    MessageLog,
    Observation,
    hash_phone,
)
from backend.sms.handler import handle_inbound_message

logger = logging.getLogger(__name__)
router = APIRouter()


class SimulateRequest(BaseModel):
    phone: str
    message: str
    image_url: str | None = None


def _dev_only_guard():
    """Return 404 in production."""
    if settings.is_production:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return None


@router.post("/simulate")
def simulate_message(req: SimulateRequest, db: Session = Depends(get_db)):
    """Send a simulated inbound message and get the full handler result."""
    guard = _dev_only_guard()
    if guard:
        return guard

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
        }

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


@router.delete("/reset")
def reset_test_data(db: Session = Depends(get_db)):
    """Clear all test data for clean runs. Dev-only."""
    guard = _dev_only_guard()
    if guard:
        return guard

    counts = {
        "coaching_responses": db.query(CoachingResponse).delete(),
        "observations": db.query(Observation).delete(),
        "coaching_sessions": db.query(CoachingSession).delete(),
        "message_log": db.query(MessageLog).delete(),
        "consent_records": db.query(ConsentRecord).delete(),
    }
    db.commit()

    return JSONResponse(content={"deleted": counts})
