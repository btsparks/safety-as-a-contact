"""Worker relationship system — profile management, tier calculation, mentor notes.

All profile logic in one place. The WorkerProfile is the persistent relationship
record read on every incoming message. InteractionAssessment rows are the raw
per-turn data that feed rolling window calculations.
"""

import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import InteractionAssessment, WorkerProfile, utcnow

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 20  # last N assessments for tier calculation
BASELINE_THRESHOLD = 5  # interactions before baseline is set
NOTES_REGEN_INTERVAL = 5  # regenerate mentor notes every N interactions


def get_or_create_profile(
    db: Session,
    phone_hash: str,
    worker_id: int | None = None,
) -> WorkerProfile:
    """Get existing profile or create a new one for this phone_hash."""
    profile = (
        db.query(WorkerProfile)
        .filter(WorkerProfile.phone_hash == phone_hash)
        .first()
    )

    if profile:
        # Link worker_id if we now have one and didn't before
        if worker_id and not profile.worker_id:
            profile.worker_id = worker_id
            db.commit()
        return profile

    now = utcnow()
    profile = WorkerProfile(
        phone_hash=phone_hash,
        worker_id=worker_id,
        current_tier=1,
        tier_updated_at=now,
        total_sessions=0,
        total_turns=0,
        first_interaction_at=now,
        last_interaction_at=now,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def save_interaction_assessment(
    db: Session,
    phone_hash: str,
    session_id: int | None,
    observation_id: int | None,
    coaching_response_id: int | None,
    result,
    observation_text: str,
) -> InteractionAssessment:
    """Save a per-turn assessment row from a CoachingResult.

    Args:
        result: A CoachingResult instance from the coaching engine.
        observation_text: The worker's raw message text.
    """
    ia = InteractionAssessment(
        phone_hash=phone_hash,
        session_id=session_id,
        observation_id=observation_id,
        coaching_response_id=coaching_response_id,
        turn_number=result.turn_number,
        response_mode=result.response_mode,
        hazard_present=bool(result.hazard_category and result.hazard_category != "behavioral"),
        hazard_category=result.hazard_category,
        specificity_score=result.specificity_score,
        worker_engagement=result.worker_engagement or "medium",
        worker_confidence=result.worker_confidence or "uncertain",
        teachable_moment=result.teachable_moment,
        suggested_next_direction=result.suggested_next_direction or "",
        has_photo=result.has_photo,
        worker_asked_question="?" in observation_text,
        worker_text_length=len(observation_text),
    )
    db.add(ia)
    db.commit()
    db.refresh(ia)
    return ia


def _get_recent_assessments(
    db: Session,
    phone_hash: str,
    limit: int = ROLLING_WINDOW,
) -> list[InteractionAssessment]:
    """Get the most recent assessments for tier calculation."""
    return (
        db.query(InteractionAssessment)
        .filter(InteractionAssessment.phone_hash == phone_hash)
        .order_by(InteractionAssessment.created_at.desc())
        .limit(limit)
        .all()
    )


def calculate_tier(
    assessments: list[InteractionAssessment],
    current_tier: int,
) -> int:
    """Calculate tier from rolling window of assessments.

    Weighted composite:
    - Specificity (25%) -- avg specificity_score / 4.0
    - Engagement depth (20%) -- rate of high engagement
    - Confidence (15%) -- rate of confident responses
    - Hazard accuracy (15%) -- rate of real hazard identification
    - Detail level (10%) -- avg text length / 100
    - Initiative (10%) -- (question rate + photo rate) / 2
    - Teaching moments (5%) -- count / 3

    Score >= 0.75 -> Tier 4, >= 0.50 -> Tier 3, >= 0.25 -> Tier 2, else Tier 1.
    Clamped to max +1/-1 from current tier.
    """
    if not assessments:
        return current_tier

    n = len(assessments)

    # Specificity (25%) -- avg specificity_score / 4.0, capped at 1.0
    avg_spec = sum(a.specificity_score or 0 for a in assessments) / n
    specificity = min(avg_spec / 4.0, 1.0)

    # Engagement depth (20%) -- rate of high engagement
    high_engagement = sum(1 for a in assessments if a.worker_engagement == "high") / n

    # Confidence (15%) -- rate of confident responses
    confident = sum(1 for a in assessments if a.worker_confidence == "confident") / n

    # Hazard accuracy (15%) -- rate of real hazard identification
    hazard_accuracy = sum(1 for a in assessments if a.hazard_present) / n

    # Detail level (10%) -- avg text length / 100, capped at 1.0
    avg_length = sum(a.worker_text_length or 0 for a in assessments) / n
    detail = min(avg_length / 100.0, 1.0)

    # Initiative (10%) -- (question rate + photo rate) / 2
    question_rate = sum(1 for a in assessments if a.worker_asked_question) / n
    photo_rate = sum(1 for a in assessments if a.has_photo) / n
    initiative = (question_rate + photo_rate) / 2

    # Teaching moments (5%) -- count / 3, capped at 1.0
    teachable_count = sum(1 for a in assessments if a.teachable_moment)
    teaching = min(teachable_count / 3.0, 1.0)

    # Weighted composite
    score = (
        specificity * 0.25
        + high_engagement * 0.20
        + confident * 0.15
        + hazard_accuracy * 0.15
        + detail * 0.10
        + initiative * 0.10
        + teaching * 0.05
    )

    # Map score to tier
    if score >= 0.75:
        raw_tier = 4
    elif score >= 0.50:
        raw_tier = 3
    elif score >= 0.25:
        raw_tier = 2
    else:
        raw_tier = 1

    # Clamp to max +1/-1 from current tier
    clamped = max(current_tier - 1, min(current_tier + 1, raw_tier))
    # Never go below 1
    return max(1, clamped)


def update_worker_profile(
    db: Session,
    profile: WorkerProfile,
    is_new_session: bool,
) -> None:
    """Recompute rolling stats and tier from recent assessments."""
    now = utcnow()
    assessments = _get_recent_assessments(db, profile.phone_hash)

    if not assessments:
        return

    n = len(assessments)

    # Update counters
    profile.total_turns += 1
    if is_new_session:
        profile.total_sessions += 1
    profile.last_interaction_at = now

    # Rolling averages
    profile.avg_specificity = sum(a.specificity_score or 0 for a in assessments) / n
    profile.avg_engagement_depth = sum(a.turn_number or 0 for a in assessments) / n
    profile.hazard_accuracy_rate = sum(1 for a in assessments if a.hazard_present) / n
    profile.photo_rate = sum(1 for a in assessments if a.has_photo) / n

    # Progression markers (sticky -- once True, stay True)
    latest = assessments[0]
    if latest.teachable_moment:
        profile.teachable_moments_count += 1

    # Dominant patterns
    engagements = [a.worker_engagement for a in assessments if a.worker_engagement]
    if engagements:
        profile.dominant_engagement = Counter(engagements).most_common(1)[0][0]

    confidences = [a.worker_confidence for a in assessments if a.worker_confidence]
    if confidences:
        profile.dominant_confidence = Counter(confidences).most_common(1)[0][0]

    hazard_cats = [a.hazard_category for a in assessments if a.hazard_category]
    if hazard_cats:
        profile.most_common_hazard_category = Counter(hazard_cats).most_common(1)[0][0]

    # Tier calculation
    old_tier = profile.current_tier
    new_tier = calculate_tier(assessments, old_tier)
    if new_tier != old_tier:
        profile.current_tier = new_tier
        profile.tier_updated_at = now
        logger.info(
            "Worker %s tier changed: %d -> %d",
            profile.phone_hash[:12], old_tier, new_tier,
        )

    # Baseline check
    if not profile.baseline_complete and profile.total_turns >= BASELINE_THRESHOLD:
        profile.baseline_complete = True
        profile.baseline_completed_at = now
        profile.baseline_tier = profile.current_tier
        logger.info(
            "Worker %s baseline complete at tier %d",
            profile.phone_hash[:12], profile.current_tier,
        )

    db.commit()


def should_regenerate_notes(
    profile: WorkerProfile,
    assessment: InteractionAssessment,
) -> bool:
    """Determine if mentor notes should be regenerated.

    Triggers:
    - Every NOTES_REGEN_INTERVAL interactions
    - On tier change (detected by checking if tier_updated_at is recent)
    - On teachable moment
    """
    if not settings.anthropic_api_key:
        return False

    if assessment.teachable_moment:
        return True

    if profile.total_turns > 0 and profile.total_turns % NOTES_REGEN_INTERVAL == 0:
        return True

    return False


def generate_mentor_notes(db: Session, profile: WorkerProfile) -> str:
    """Generate AI mentor notes via Claude API. No-op if no API key.

    Returns the generated notes string (also saved to profile).
    """
    if not settings.anthropic_api_key:
        return profile.mentor_notes or ""

    assessments = _get_recent_assessments(db, profile.phone_hash)
    if not assessments:
        return profile.mentor_notes or ""

    # Build context for the notes generation
    summary_lines = []
    for a in reversed(assessments):  # chronological order
        line = (
            f"Turn {a.turn_number}: mode={a.response_mode}, "
            f"hazard={a.hazard_present}, specificity={a.specificity_score}, "
            f"engagement={a.worker_engagement}, confidence={a.worker_confidence}, "
            f"teachable={a.teachable_moment}, photo={a.has_photo}, "
            f"text_len={a.worker_text_length}"
        )
        summary_lines.append(line)

    context = "\n".join(summary_lines)

    prompt = (
        "You are writing internal mentor notes for a safety coaching AI. "
        "These notes tell the coaching AI who this worker is, so it can adapt "
        "its approach. Write 3-5 sentences in the voice of an experienced "
        "construction mentor describing this worker's patterns, growth, and "
        "areas to develop. Be specific and practical — this is for the AI's "
        "eyes only, not the worker's.\n\n"
        f"Worker stats:\n"
        f"- Total sessions: {profile.total_sessions}\n"
        f"- Total turns: {profile.total_turns}\n"
        f"- Current tier: {profile.current_tier}/4\n"
        f"- Avg specificity: {profile.avg_specificity:.1f}/5\n"
        f"- Hazard accuracy: {profile.hazard_accuracy_rate:.0%}\n"
        f"- Photo rate: {profile.photo_rate:.0%}\n"
        f"- Dominant engagement: {profile.dominant_engagement}\n"
        f"- Dominant confidence: {profile.dominant_confidence}\n"
        f"- Most common hazard: {profile.most_common_hazard_category or 'none yet'}\n"
        f"- Teachable moments: {profile.teachable_moments_count}\n"
        f"- Baseline complete: {profile.baseline_complete}\n\n"
        f"Recent interaction log:\n{context}\n\n"
        "Write the mentor notes now (3-5 sentences, practical, specific):"
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
        )
        notes = resp.content[0].text.strip()
    except Exception as e:
        logger.error("Failed to generate mentor notes: %s", e)
        return profile.mentor_notes or ""

    # Save to profile
    profile.mentor_notes = notes
    profile.mentor_notes_updated_at = utcnow()
    profile.mentor_notes_version = (profile.mentor_notes_version or 0) + 1
    db.commit()

    logger.info(
        "Regenerated mentor notes for %s (version %d)",
        profile.phone_hash[:12], profile.mentor_notes_version,
    )
    return notes
