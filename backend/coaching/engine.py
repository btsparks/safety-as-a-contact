"""Coaching engine — multi-turn conversation management + mock/live Claude API.

Source of truth: .claude/skills/prompt-architecture/SKILL.md
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
    response_mode: str  # alert/validate/nudge/probe/affirm
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
     "environmental", 4, "alert"),
    (["rebar", "impalement", "exposed", "caps", "mushroom"],
     "environmental", 4, "alert"),
    (["electrocution", "shock", "energized", "live wire", "power line", "electrical"],
     "equipment", 5, "alert"),
    (["trench", "excavation", "cave", "collapse", "shoring"],
     "environmental", 5, "alert"),
    (["fire", "explosion", "gas leak", "flammable"],
     "environmental", 5, "alert"),
    (["guard", "blade", "saw", "cut", "laceration", "amputation"],
     "equipment", 3, "validate"),
    (["ppe", "glasses", "gloves", "hard hat", "helmet", "vest", "boots", "footwear",
      "steel toe", "steel toes", "safety shoes", "hi-vis", "high vis", "goggles",
      "face shield", "respirator"],
     "procedural", 2, "validate"),
    (["housekeeping", "trash", "debris", "clutter", "trip", "slip"],
     "environmental", 2, "nudge"),
    (["noise", "hearing", "loud", "ear plug", "ear pro", "earplug"],
     "environmental", 2, "nudge"),
    (["lifting", "back", "strain", "ergonomic", "posture", "heavy"],
     "ergonomic", 2, "nudge"),
    (["good", "nice", "safe", "proud", "team", "crew", "great"],
     "behavioral", 1, "affirm"),
]


# Mock responses — professional tone, photo-first workflow.
# - Question-first (3:1 ratio)
# - Specific, not generic
# - No corporate language, no brand sign-off
# - ONE observation, invites reply
# - Professional but approachable voice

_MOCK_RESPONSES: dict[str, list[str]] = {
    "alert": [
        "That wall is bowing. Get everyone back 20 feet. Do not go near it until it is shored.",
        "Exposed line right there. Kill the power before anyone touches that panel.",
        "That trench has no box past the bend. Nobody goes in until it is shored.",
    ],
    "validate": [
        "Trust that instinct — that is too close without a line. What is your plan to flag it for the crew?",
        "Good call on that one. Most people walk right past it. How are you keeping others back?",
        "That is a real catch. What tipped you off?",
    ],
    "nudge": [
        "Pour setup looks solid. What is the plan for those cords if that area takes on water?",
        "Housekeeping on the deck looks good. What about that material stack — anything shifting?",
        "Staging looks right. What happens to this area when the crane starts swinging loads this afternoon?",
    ],
    "probe": [
        "Busy site — what is happening right behind where you took this?",
        "Deck looks clean. What changes here later in the shift?",
        "Everything looks set. What is the weather doing to this area by end of day?",
    ],
    "affirm": [
        "Barricade placement is textbook — keeps foot traffic clear of the swing radius.",
        "Clean layout, cords routed, materials staged right. That is how it is done.",
        "Solid eye. Stay sharp out there.",
    ],
}

_MOCK_PHOTO_RESPONSES: dict[str, list[str]] = {
    "alert": [
        "Unguarded edge with foot traffic right there. Get a barricade up now.",
    ],
    "validate": [
        "Right instinct — that setup does not look stable. What is your plan?",
    ],
    "nudge": [
        "Work area looks good. What about overhead — anything rigged above this spot?",
    ],
    "probe": [
        "A lot going on here. What area are you working in and what is the project?",
        "Which crew is on this? Knowing the trade helps give a better read.",
    ],
    "affirm": [
        "Clean setup. Everything staged and routed properly.",
    ],
}

_MOCK_NO_PHOTO_RESPONSES: list[str] = [
    "Send a photo of the area and let me know what you are working on.",
    "Hard to give a good read without seeing it. Send a photo of what you are looking at.",
    "Send a picture of the work area. That is the best way to talk through it.",
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

    # Default: moderate, ask for more info
    return "procedural", 3, "probe", language


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
        responses = _MOCK_RESPONSES.get(mode, _MOCK_RESPONSES["probe"])

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

    # Override to alert for severity >= 5
    if severity >= 5:
        mode = "alert"

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
                "suggested_mode": data.get("suggested_mode", "probe"),
                "language": data.get("language", "en"),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return {"hazard_category": "procedural", "severity": 3,
            "suggested_mode": "probe", "language": "en"}


def _parse_coaching_response(text: str) -> tuple[str, dict]:
    """Parse Claude's coaching response which contains message ||| assessment JSON.

    Returns (coaching_text, assessment_dict).
    """
    if "|||" in text:
        parts = text.split("|||", 1)
        coaching_text = parts[0].strip()
        try:
            assessment = json.loads(parts[1].strip())
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
) -> CoachingResult:
    """Live coaching via Claude API. Single call with full prompt architecture."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    profile = get_trade_profile(trade)
    start = time.monotonic()
    has_photo = bool(media_urls)

    # Build system prompt from the skill spec architecture
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
    )

    # Build user message with photo support
    user_content = build_user_message(
        body=observation,
        media_urls=media_urls,
        trade_label=profile["label"],
        experience_level=experience_level,
    )

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        temperature=0.3,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    prompt_tokens = resp.usage.input_tokens
    completion_tokens = resp.usage.output_tokens
    raw_text = resp.content[0].text

    # Parse response + assessment
    coaching_text, assessment = _parse_coaching_response(raw_text)

    # Validate length — truncate if over 320 chars
    if len(coaching_text) > 320:
        coaching_text = coaching_text[:317] + "..."

    # Extract assessment fields
    mode = assessment.get("response_mode", "probe")
    hazard_category = assessment.get("hazard_category") or "procedural"
    severity_guess = 3
    if assessment.get("hazard_present") and mode == "alert":
        severity_guess = 5
    elif assessment.get("hazard_present") and mode == "nudge":
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
        specificity_score=assessment.get("specificity_score", 0),
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

    # Attach session ID
    if session:
        result.session_id = session.id

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
