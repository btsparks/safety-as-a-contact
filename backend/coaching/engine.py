"""Coaching engine — multi-turn conversation management + mock/live Claude API.

Document-grounded + behavioral reflection model.
Source of truth: docs/PIVOT_PLAN.md
"""

import json
import logging
import re
import time
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.coaching.prompts import (
    build_classification_prompt,
    build_system_prompt,
    build_user_message,
)
from backend.coaching.trades import get_trade_profile
from backend.coaching.profile import (
    generate_mentor_notes,
    get_or_create_profile,
    save_interaction_assessment,
    should_regenerate_notes,
    update_worker_profile,
)
from backend.models import CoachingResponse, CoachingSession, Observation, utcnow

logger = logging.getLogger(__name__)


# --- Result model ---

class CoachingResult(BaseModel):
    """Result from the coaching engine — identical structure for mock and live."""

    response_text: str
    response_mode: str  # reference/reflect/connect (v2) or alert/validate/nudge/probe/affirm (v1 compat)
    hazard_category: str
    severity: int  # 1-5
    language: str  # en/es
    model_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    is_mock: bool = False
    has_photo: bool = False
    turn_number: int = 1
    session_id: int | None = None
    # Document references
    document_ids: list[int] = []
    document_referenced: bool = False
    trade_match: bool = True
    # Assessment metadata (from AI, not shown to worker)
    specificity_score: int = 0
    worker_engagement: str = ""
    worker_confidence: str = ""
    teachable_moment: bool = False
    suggested_next_direction: str = ""


# --- Session management ---

def get_or_create_session(
    db: Session,
    phone_hash: str,
    worker_id: int | None = None,
    worker_tier: int = 1,
) -> CoachingSession:
    """Find the active session for this phone or create a new one.

    Rules from the skill spec:
    - If no reply in 30 min, session is paused
    - If they text again within 4 hours, resume same session
    - After 4 hours, start a new session
    """
    now = utcnow()
    timeout_minutes = settings.session_timeout_minutes

    # Look for most recent non-closed session for this phone
    session = (
        db.query(CoachingSession)
        .filter(
            CoachingSession.phone_hash == phone_hash,
            CoachingSession.is_closed == False,
        )
        .order_by(CoachingSession.last_activity_at.desc())
        .first()
    )

    if session:
        # Check if session has timed out (4 hours default)
        # Handle naive vs aware datetimes (SQLite returns naive)
        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        elapsed = (now - last_activity).total_seconds() / 60
        if elapsed <= timeout_minutes:
            # Resume session
            session.last_activity_at = now
            session.turn_count += 1
            db.commit()
            return session
        else:
            # Close old session, create new
            session.is_closed = True
            session.ended_at = now
            db.commit()

    # Create new session
    new_session = CoachingSession(
        phone_hash=phone_hash,
        worker_id=worker_id,
        turn_count=1,
        worker_tier=worker_tier,
        started_at=now,
        last_activity_at=now,
        response_modes_used="[]",
        media_urls="[]",
        progression_markers="{}",
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


def get_thread_history(db: Session, session_id: int, limit: int = 6) -> str:
    """Build thread history string from previous observations + responses in this session.

    Returns formatted text for inclusion in the system prompt.
    """
    observations = (
        db.query(Observation)
        .filter(Observation.session_id == session_id)
        .order_by(Observation.created_at.asc())
        .limit(limit)
        .all()
    )

    if not observations:
        return ""

    lines = []
    for obs in observations:
        has_photo = bool(obs.media_urls and obs.media_urls != "[]")
        photo_note = " [with photo]" if has_photo else ""
        lines.append(f"Worker: {obs.raw_text}{photo_note}")

        # Get the coaching response for this observation
        for cr in obs.coaching_responses:
            lines.append(f"Coach: {cr.response_text}")
            break  # only first response

    return "\n".join(lines)


def update_session_metadata(
    db: Session,
    session: CoachingSession,
    result: CoachingResult,
    media_urls: list[str] | None = None,
) -> None:
    """Update session with data from the latest coaching result."""
    # Track response modes used
    modes = json.loads(session.response_modes_used or "[]")
    if result.response_mode not in modes:
        modes.append(result.response_mode)
    session.response_modes_used = json.dumps(modes)

    # Track media
    if media_urls:
        existing = json.loads(session.media_urls or "[]")
        existing.extend(media_urls)
        session.media_urls = json.dumps(existing)

    # Update from assessment
    if result.hazard_category and result.hazard_category != "behavioral":
        session.hazard_identified = True
        session.hazard_category = result.hazard_category
    if result.teachable_moment:
        session.teachable_moment = True
    if result.worker_engagement:
        session.session_sentiment = result.worker_engagement
    if result.suggested_next_direction == "close":
        session.coaching_direction = "closing"
    elif result.suggested_next_direction:
        session.coaching_direction = result.suggested_next_direction

    db.commit()


# --- Mock mode (no API key) ---

_KEYWORD_HAZARDS: list[tuple[list[str], str, int, str]] = [
    (["fall", "height", "edge", "ledge", "roof", "ladder", "scaffold", "harness",
      "tie off", "tie-off"],
     "environmental", 4, "reference"),
    (["rebar", "impalement", "exposed", "caps", "mushroom"],
     "environmental", 4, "reference"),
    (["electrocution", "shock", "energized", "live wire", "power line", "electrical"],
     "equipment", 5, "reference"),
    (["trench", "excavation", "cave", "collapse", "shoring"],
     "environmental", 5, "reference"),
    (["fire", "explosion", "gas leak", "flammable"],
     "environmental", 5, "reference"),
    (["guard", "blade", "saw", "cut", "laceration", "amputation"],
     "equipment", 3, "reference"),
    (["ppe", "glasses", "gloves", "hard hat", "helmet", "vest", "boots", "footwear",
      "steel toe", "steel toes", "safety shoes", "hi-vis", "high vis", "goggles",
      "face shield", "respirator"],
     "procedural", 2, "reference"),
    (["housekeeping", "trash", "debris", "clutter", "trip", "slip"],
     "environmental", 2, "reflect"),
    (["noise", "hearing", "loud", "ear plug", "ear pro", "earplug"],
     "environmental", 2, "reflect"),
    (["lifting", "back", "strain", "ergonomic", "posture", "heavy"],
     "ergonomic", 2, "reflect"),
    (["good", "nice", "safe", "proud", "team", "crew", "great"],
     "behavioral", 1, "reflect"),
]


# Mock responses — document-grounded + reflective model.
# Three modes: reference, reflect, connect.
# No technical advice, no safety judgments.

_MOCK_RESPONSES: dict[str, list[str]] = {
    "reference": [
        "Got your photo. Your site safety plan covers fall protection for this type of work in Section 3.2. Who else on your crew has seen this area today?",
        "That area shows up in the project safety plan under housekeeping standards. Has this been flagged at a toolbox talk yet?",
        "The company had a similar incident back in 2023 (Incident #2023-041). Has anyone on your crew gone over that one?",
    ],
    "reflect": [
        "Got your photo of that area. Nothing in the current site docs covers this specifically — worth bringing up with your foreman. What is your read on it?",
        "Interesting catch. What made you stop and take this photo?",
        "Got your photo — lot going on over there. What caught your eye about this area?",
    ],
    "connect": [
        "Got your photo. That is outside your usual work area — how does this connect to what your crew is doing today?",
        "That is a different setup than what you usually send. What brought you over to this area?",
        "Good eye spotting that. How does this affect the work your crew has going on nearby?",
    ],
}

_MOCK_PHOTO_RESPONSES: dict[str, list[str]] = {
    "reference": [
        "Got your photo. The site safety plan has a section on this type of work. Who else on the crew has seen this area?",
    ],
    "reflect": [
        "Got your photo — lot going on there. What caught your eye about this spot?",
    ],
    "connect": [
        "Got your photo. How does this connect to the work your crew is doing today?",
    ],
}

_MOCK_NO_PHOTO_RESPONSES: list[str] = [
    "Got your message. What does the area look like — can you send a photo so the full picture is clear?",
    "Sounds like something worth a look. Can you send a photo of what you are seeing out there?",
    "Copy that. A photo of the area would help pull up the right project documents — can you send one?",
]


def _classify_mock(observation: str) -> tuple[str, int, str, str]:
    """Keyword-based classification for mock mode. Returns (category, severity, mode, language)."""
    text = observation.lower()

    # Language detection (basic)
    spanish_words = {"peligro", "riesgo", "caida", "caída", "andamio", "casco",
                     "seguridad", "herramienta", "trabajo"}
    language = "es" if any(w in text for w in spanish_words) else "en"

    for keywords, category, severity, mode in _KEYWORD_HAZARDS:
        if any(kw in text for kw in keywords):
            return category, severity, mode, language

    # Default: moderate, reflective question
    return "procedural", 3, "reflect", language


def _generate_mock_response(
    mode: str,
    has_photo: bool = False,
    turn_number: int = 1,
) -> str:
    """Generate a framework-compliant mock coaching response."""
    import random

    # No photo on first turn — ask for one
    if not has_photo and turn_number == 1:
        idx = 0 % len(_MOCK_NO_PHOTO_RESPONSES)
        return _MOCK_NO_PHOTO_RESPONSES[idx]

    if has_photo and mode in _MOCK_PHOTO_RESPONSES:
        responses = _MOCK_PHOTO_RESPONSES[mode]
    else:
        responses = _MOCK_RESPONSES.get(mode, _MOCK_RESPONSES["reflect"])

    # Use turn_number as seed for deterministic-ish selection in tests
    idx = (turn_number - 1) % len(responses)
    return responses[idx]


def coach_mock(
    observation: str,
    trade: str | None = None,
    experience_level: str = "entry",
    media_urls: list[str] | None = None,
    turn_number: int = 1,
) -> CoachingResult:
    """Mock coaching — no API call. Framework-compliant responses."""
    start = time.monotonic()
    category, severity, mode, language = _classify_mock(observation)

    # High severity -> reference mode (check documents first)
    if severity >= 5:
        mode = "reference"

    has_photo = bool(media_urls)
    response_text = _generate_mock_response(mode, has_photo, turn_number)
    elapsed = int((time.monotonic() - start) * 1000)

    return CoachingResult(
        response_text=response_text,
        response_mode=mode,
        hazard_category=category,
        severity=severity,
        language=language,
        model_used="mock",
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=elapsed,
        is_mock=True,
        has_photo=has_photo,
        turn_number=turn_number,
    )


# --- Live mode (Claude API) ---

def _parse_classification(text: str) -> dict:
    """Extract JSON from Claude's classification response."""
    match = re.search(r"\{[^}]+\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return {
                "hazard_category": data.get("hazard_category", "procedural"),
                "severity": max(1, min(5, int(data.get("severity", 3)))),
                "suggested_mode": data.get("suggested_mode", "reflect"),
                "language": data.get("language", "en"),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return {"hazard_category": "procedural", "severity": 3,
            "suggested_mode": "reflect", "language": "en"}


def _parse_coaching_response(text: str) -> tuple[str, dict]:
    """Parse Claude's coaching response which contains message ||| assessment JSON.

    The model sometimes wraps JSON in ||| ... ||| (with trailing separator).
    Returns (coaching_text, assessment_dict).
    """
    if "|||" in text:
        parts = text.split("|||", 1)
        coaching_text = parts[0].strip()
        # Strip any trailing ||| the model may have added
        json_part = parts[1].strip().rstrip("|").strip()
        try:
            assessment = json.loads(json_part)
        except (json.JSONDecodeError, IndexError):
            assessment = {}
    else:
        coaching_text = text.strip()
        assessment = {}

    return coaching_text, assessment


def coach_live(
    observation: str,
    trade: str | None = None,
    experience_level: str = "entry",
    media_urls: list[str] | None = None,
    turn_number: int = 1,
    thread_history: str = "",
    worker_tier: int = 1,
    preferred_language: str = "en",
    mentor_notes: str = "",
    # NEW parameters for document-grounded model
    document_context: str = "",
    worker_name: str = "",
    project_name: str = "",
    project_context: str = "",
) -> CoachingResult:
    """Live coaching via Claude API. Single call with full prompt architecture."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    profile = get_trade_profile(trade)
    start = time.monotonic()
    has_photo = bool(media_urls)

    # Build system prompt from the document-grounded architecture
    system_prompt = build_system_prompt(
        trade=trade or "general",
        trade_label=profile["label"],
        experience_level=experience_level,
        preferred_language=preferred_language,
        worker_tier=worker_tier,
        turn_number=turn_number,
        thread_history=thread_history,
        has_photo=has_photo,
        coaching_focus=profile["coaching_focus"],
        mentor_notes=mentor_notes,
        document_context=document_context,
        worker_name=worker_name,
        project_name=project_name,
        project_context=project_context,
    )

    # Build user message with photo support
    user_content = build_user_message(
        body=observation,
        media_urls=media_urls,
        trade_label=profile["label"],
        experience_level=experience_level,
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.BadRequestError as e:
        # Gracefully handle bad requests (oversized images, invalid URLs, etc.)
        logger.warning("Claude API BadRequest, falling back to mock: %s", e)
        return coach_mock(observation, trade, experience_level, media_urls=None, turn_number=turn_number)

    prompt_tokens = resp.usage.input_tokens
    completion_tokens = resp.usage.output_tokens
    raw_text = resp.content[0].text

    # Log raw response for debugging assessment parsing
    has_separator = "|||" in raw_text
    logger.info(
        "Claude raw response (%d tokens, has_|||=%s): %s",
        completion_tokens, has_separator, raw_text[:200],
    )

    # Parse response + assessment
    coaching_text, assessment = _parse_coaching_response(raw_text)

    # Validate length — truncate if over 320 chars
    if len(coaching_text) > 320:
        coaching_text = coaching_text[:317] + "..."

    # Extract assessment fields
    mode = assessment.get("response_mode", "reflect")
    hazard_category = assessment.get("hazard_category") or "procedural"
    severity_guess = 3
    if assessment.get("document_referenced") and mode == "reference":
        severity_guess = 3
    elif hazard_category and hazard_category != "behavioral":
        severity_guess = 3

    elapsed = int((time.monotonic() - start) * 1000)

    return CoachingResult(
        response_text=coaching_text,
        response_mode=mode,
        hazard_category=hazard_category,
        severity=severity_guess,
        language=assessment.get("language", preferred_language),
        model_used="claude-haiku-4-5-20251001",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=elapsed,
        is_mock=False,
        has_photo=has_photo,
        turn_number=turn_number,
        document_referenced=assessment.get("document_referenced", False),
        trade_match=assessment.get("trade_match", True),
        specificity_score=int(assessment.get("specificity_score") or 0),
        worker_engagement=assessment.get("worker_engagement", ""),
        worker_confidence=assessment.get("worker_confidence", ""),
        teachable_moment=assessment.get("teachable_moment", False),
        suggested_next_direction=assessment.get("suggested_next_direction", ""),
    )


# --- Public API ---

def run_coaching(
    db: Session,
    observation_text: str,
    trade: str | None = None,
    experience_level: str = "entry",
    observation_id: int | None = None,
    media_urls: list[str] | None = None,
    phone_hash: str = "",
    worker_id: int | None = None,
    worker_tier: int = 1,
    preferred_language: str = "en",
    # NEW parameters for document-grounded model
    document_context: str = "",
    worker_name: str = "",
    project_name: str = "",
    project_context: str = "",
) -> CoachingResult:
    """Run the coaching pipeline. Uses live mode if API key is set, mock otherwise.

    Manages conversation sessions, creates CoachingResponse records,
    updates Observation + CoachingSession metadata, and maintains
    the worker's longitudinal profile.
    """
    # Resolve worker profile and tier
    worker_profile = None
    mentor_notes = ""
    is_new_session = False

    if phone_hash:
        worker_profile = get_or_create_profile(db, phone_hash, worker_id)
        worker_tier = worker_profile.current_tier
        mentor_notes = worker_profile.mentor_notes or ""

    # Get or create conversation session
    session = None
    turn_number = 1
    thread_history = ""

    if phone_hash:
        old_session_count = (
            db.query(CoachingSession)
            .filter(CoachingSession.phone_hash == phone_hash)
            .count()
        )
        session = get_or_create_session(db, phone_hash, worker_id, worker_tier)
        new_session_count = (
            db.query(CoachingSession)
            .filter(CoachingSession.phone_hash == phone_hash)
            .count()
        )
        is_new_session = new_session_count > old_session_count
        turn_number = session.turn_count
        thread_history = get_thread_history(db, session.id)

    # Link observation to session
    if observation_id and session:
        obs = db.get(Observation, observation_id)
        if obs:
            obs.session_id = session.id
            db.commit()

    # Resolve worker context for document retrieval and personalization
    worker_project_id = None
    if not worker_name and phone_hash:
        from backend.models import Worker
        worker_rec = (
            db.query(Worker)
            .filter(Worker.phone_hash == phone_hash)
            .first()
        )
        if worker_rec:
            worker_name = worker_rec.first_name or ""
            worker_project_id = worker_rec.active_project_id or worker_rec.project_id
            if not trade and worker_rec.trade:
                trade = worker_rec.trade

    # Resolve project context
    if worker_project_id and not project_name:
        from backend.models import Project
        proj = db.get(Project, worker_project_id)
        if proj:
            project_name = proj.name
            project_context = proj.description or ""

    # Document retrieval — query before coaching
    document_ids: list[int] = []
    if not document_context:
        from backend.documents.retrieval import retrieve_relevant_documents
        doc_results = retrieve_relevant_documents(
            db=db,
            project_id=worker_project_id,
            trade=trade or "general",
            observation_text=observation_text,
        )
        document_context = doc_results.formatted_context
        document_ids = doc_results.document_ids

    use_live = bool(settings.anthropic_api_key)

    if use_live:
        logger.info("Coaching engine: live mode (Claude API), turn %d", turn_number)
        result = coach_live(
            observation_text,
            trade,
            experience_level,
            media_urls=media_urls,
            turn_number=turn_number,
            thread_history=thread_history,
            worker_tier=worker_tier,
            preferred_language=preferred_language,
            mentor_notes=mentor_notes,
            document_context=document_context,
            worker_name=worker_name,
            project_name=project_name,
            project_context=project_context,
        )
    else:
        logger.info("Coaching engine: mock mode, turn %d", turn_number)
        result = coach_mock(
            observation_text,
            trade,
            experience_level,
            media_urls=media_urls,
            turn_number=turn_number,
        )

    # Attach document references to result
    result.document_ids = document_ids
    result.document_referenced = bool(document_ids)

    # Attach session ID
    if session:
        result.session_id = session.id

    # Log document references
    if document_ids and phone_hash:
        from backend.models import DocumentReference
        for doc_id in document_ids:
            ref = DocumentReference(
                phone_hash=phone_hash,
                session_id=session.id if session else None,
                document_id=doc_id,
                observation_id=observation_id,
            )
            db.add(ref)
        # Update session with doc references
        if session:
            import json as _json
            existing_refs = _json.loads(session.document_references_json or "[]")
            existing_refs.extend(document_ids)
            session.document_references_json = _json.dumps(existing_refs)
        db.commit()

    # Persist CoachingResponse
    cr = CoachingResponse(
        observation_id=observation_id,
        response_mode=result.response_mode,
        response_text=result.response_text,
        hazard_category=result.hazard_category,
        severity=result.severity,
        model_used=result.model_used,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=result.latency_ms,
    )
    db.add(cr)

    # Update observation with classification if linked
    if observation_id:
        obs = db.get(Observation, observation_id)
        if obs:
            obs.hazard_category = result.hazard_category
            obs.severity = result.severity
            obs.language = result.language

    db.commit()

    # Update session metadata
    if session:
        update_session_metadata(db, session, result, media_urls)

    # Save interaction assessment and update profile
    if phone_hash and worker_profile:
        ia = save_interaction_assessment(
            db,
            phone_hash=phone_hash,
            session_id=session.id if session else None,
            observation_id=observation_id,
            coaching_response_id=cr.id,
            result=result,
            observation_text=observation_text,
        )
        update_worker_profile(db, worker_profile, is_new_session)

        # Regenerate mentor notes if needed
        if should_regenerate_notes(worker_profile, ia):
            generate_mentor_notes(db, worker_profile)

    return result
