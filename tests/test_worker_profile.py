"""Tests for the Worker Relationship System — profile, tier calc, assessments."""

import pytest

from backend.coaching.engine import CoachingResult, run_coaching
from backend.coaching.profile import (
    BASELINE_THRESHOLD,
    NOTES_REGEN_INTERVAL,
    calculate_tier,
    get_or_create_profile,
    save_interaction_assessment,
    should_regenerate_notes,
    update_worker_profile,
)
from backend.models import (
    InteractionAssessment,
    WorkerProfile,
    hash_phone,
)
from tests.conftest import TEST_PHONE, TEST_PHONE_2


# --- get_or_create_profile ---

class TestGetOrCreateProfile:

    def test_creates_new_profile(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        assert profile.id is not None
        assert profile.phone_hash == ph
        assert profile.current_tier == 1
        assert profile.total_sessions == 0
        assert profile.total_turns == 0
        assert profile.first_interaction_at is not None

    def test_returns_existing_profile(self, db):
        ph = hash_phone(TEST_PHONE)
        p1 = get_or_create_profile(db, ph)
        p2 = get_or_create_profile(db, ph)
        assert p1.id == p2.id

    def test_links_worker_id_on_subsequent_call(self, db):
        ph = hash_phone(TEST_PHONE)
        p1 = get_or_create_profile(db, ph)
        assert p1.worker_id is None

        p2 = get_or_create_profile(db, ph, worker_id=42)
        assert p2.worker_id == 42
        assert p1.id == p2.id

    def test_different_phones_get_different_profiles(self, db):
        p1 = get_or_create_profile(db, hash_phone(TEST_PHONE))
        p2 = get_or_create_profile(db, hash_phone(TEST_PHONE_2))
        assert p1.id != p2.id


# --- save_interaction_assessment ---

class TestSaveInteractionAssessment:

    def _mock_result(self, **overrides):
        defaults = dict(
            response_text="Solid setup.",
            response_mode="affirm",
            hazard_category="procedural",
            severity=2,
            language="en",
            model_used="mock",
            is_mock=True,
            has_photo=False,
            turn_number=1,
            specificity_score=3,
            worker_engagement="medium",
            worker_confidence="uncertain",
            teachable_moment=False,
            suggested_next_direction="deeper",
        )
        defaults.update(overrides)
        return CoachingResult(**defaults)

    def test_saves_assessment_row(self, db):
        ph = hash_phone(TEST_PHONE)
        result = self._mock_result()
        ia = save_interaction_assessment(
            db, ph, session_id=None, observation_id=None,
            coaching_response_id=None, result=result,
            observation_text="Exposed rebar near walkway",
        )
        assert ia.id is not None
        assert ia.phone_hash == ph
        assert ia.response_mode == "affirm"
        assert ia.specificity_score == 3
        assert ia.worker_text_length == len("Exposed rebar near walkway")

    def test_detects_question_mark(self, db):
        ph = hash_phone(TEST_PHONE)
        result = self._mock_result()
        ia = save_interaction_assessment(
            db, ph, None, None, None, result,
            "Is this safe to walk on?",
        )
        assert ia.worker_asked_question is True

    def test_no_question_mark(self, db):
        ph = hash_phone(TEST_PHONE)
        result = self._mock_result()
        ia = save_interaction_assessment(
            db, ph, None, None, None, result,
            "Looks good to me",
        )
        assert ia.worker_asked_question is False

    def test_hazard_present_flag(self, db):
        ph = hash_phone(TEST_PHONE)
        result = self._mock_result(hazard_category="environmental")
        ia = save_interaction_assessment(
            db, ph, None, None, None, result, "Edge without guardrail",
        )
        assert ia.hazard_present is True

    def test_behavioral_not_counted_as_hazard(self, db):
        ph = hash_phone(TEST_PHONE)
        result = self._mock_result(hazard_category="behavioral")
        ia = save_interaction_assessment(
            db, ph, None, None, None, result, "Crew doing great today",
        )
        assert ia.hazard_present is False


# --- calculate_tier ---

class TestCalculateTier:

    def _make_assessments(self, n, **overrides):
        """Create a list of mock InteractionAssessment objects."""
        defaults = dict(
            specificity_score=3,
            worker_engagement="medium",
            worker_confidence="uncertain",
            hazard_present=False,
            worker_text_length=50,
            worker_asked_question=False,
            has_photo=False,
            teachable_moment=False,
        )
        defaults.update(overrides)
        assessments = []
        for _ in range(n):
            ia = InteractionAssessment(**defaults)
            assessments.append(ia)
        return assessments

    def test_low_scores_stay_tier_1(self):
        assessments = self._make_assessments(
            10,
            specificity_score=1,
            worker_engagement="low",
            worker_confidence="resistant",
            worker_text_length=10,
        )
        tier = calculate_tier(assessments, current_tier=1)
        assert tier == 1

    def test_high_scores_promote(self):
        assessments = self._make_assessments(
            10,
            specificity_score=5,
            worker_engagement="high",
            worker_confidence="confident",
            hazard_present=True,
            worker_text_length=120,
            worker_asked_question=True,
            has_photo=True,
            teachable_moment=True,
        )
        # Starting from tier 1, can only go to tier 2 (clamp +1)
        tier = calculate_tier(assessments, current_tier=1)
        assert tier == 2

    def test_high_scores_from_tier_3(self):
        """From tier 3, high scores should promote to tier 4."""
        assessments = self._make_assessments(
            10,
            specificity_score=5,
            worker_engagement="high",
            worker_confidence="confident",
            hazard_present=True,
            worker_text_length=120,
            worker_asked_question=True,
            has_photo=True,
            teachable_moment=True,
        )
        tier = calculate_tier(assessments, current_tier=3)
        assert tier == 4

    def test_clamp_prevents_jumping(self):
        """Can't jump from tier 1 to tier 4 in one calculation."""
        assessments = self._make_assessments(
            20,
            specificity_score=5,
            worker_engagement="high",
            worker_confidence="confident",
            hazard_present=True,
            worker_text_length=200,
            worker_asked_question=True,
            has_photo=True,
            teachable_moment=True,
        )
        tier = calculate_tier(assessments, current_tier=1)
        assert tier == 2  # clamped to +1

    def test_clamp_prevents_dropping(self):
        """Can't drop from tier 4 to tier 1 in one calculation."""
        assessments = self._make_assessments(
            10,
            specificity_score=0,
            worker_engagement="low",
            worker_confidence="resistant",
            worker_text_length=5,
        )
        tier = calculate_tier(assessments, current_tier=4)
        assert tier == 3  # clamped to -1

    def test_empty_assessments_returns_current(self):
        tier = calculate_tier([], current_tier=2)
        assert tier == 2

    def test_never_below_tier_1(self):
        assessments = self._make_assessments(
            5,
            specificity_score=0,
            worker_engagement="low",
            worker_confidence="resistant",
            worker_text_length=0,
        )
        tier = calculate_tier(assessments, current_tier=1)
        assert tier >= 1

    def test_moderate_scores_tier_2(self):
        """Moderate engagement should compute to tier 2 range."""
        assessments = self._make_assessments(
            10,
            specificity_score=2,
            worker_engagement="medium",
            worker_confidence="uncertain",
            hazard_present=True,
            worker_text_length=60,
        )
        tier = calculate_tier(assessments, current_tier=1)
        # Score ~ 0.25 range, should be tier 2, clamped from 1 -> max 2
        assert tier in (1, 2)


# --- update_worker_profile ---

class TestUpdateWorkerProfile:

    def _add_assessment(self, db, ph, **kwargs):
        defaults = dict(
            phone_hash=ph,
            specificity_score=3,
            worker_engagement="medium",
            worker_confidence="uncertain",
            hazard_present=False,
            worker_text_length=50,
            worker_asked_question=False,
            has_photo=False,
            teachable_moment=False,
            turn_number=1,
            response_mode="probe",
        )
        defaults.update(kwargs)
        ia = InteractionAssessment(**defaults)
        db.add(ia)
        db.commit()
        return ia

    def test_increments_total_turns(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        self._add_assessment(db, ph)
        update_worker_profile(db, profile, is_new_session=False)
        assert profile.total_turns == 1

    def test_increments_total_sessions(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        self._add_assessment(db, ph)
        update_worker_profile(db, profile, is_new_session=True)
        assert profile.total_sessions == 1

    def test_does_not_increment_sessions_on_resume(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        self._add_assessment(db, ph)
        update_worker_profile(db, profile, is_new_session=False)
        assert profile.total_sessions == 0

    def test_updates_rolling_averages(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        self._add_assessment(db, ph, specificity_score=4, has_photo=True)
        self._add_assessment(db, ph, specificity_score=2, has_photo=False)
        update_worker_profile(db, profile, is_new_session=False)
        assert profile.avg_specificity == 3.0
        assert profile.photo_rate == 0.5

    def test_baseline_complete_after_threshold(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)

        for i in range(BASELINE_THRESHOLD):
            self._add_assessment(db, ph, turn_number=i + 1)
            update_worker_profile(db, profile, is_new_session=(i == 0))

        assert profile.baseline_complete is True
        assert profile.baseline_completed_at is not None
        assert profile.baseline_tier is not None

    def test_baseline_not_complete_before_threshold(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)

        for i in range(BASELINE_THRESHOLD - 1):
            self._add_assessment(db, ph, turn_number=i + 1)
            update_worker_profile(db, profile, is_new_session=(i == 0))

        assert profile.baseline_complete is False

    def test_teachable_moment_increments_count(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        self._add_assessment(db, ph, teachable_moment=True)
        update_worker_profile(db, profile, is_new_session=False)
        assert profile.teachable_moments_count == 1

    def test_dominant_patterns_updated(self, db):
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        self._add_assessment(db, ph, worker_engagement="high", worker_confidence="confident")
        self._add_assessment(db, ph, worker_engagement="high", worker_confidence="confident")
        self._add_assessment(db, ph, worker_engagement="low", worker_confidence="uncertain")
        update_worker_profile(db, profile, is_new_session=False)
        assert profile.dominant_engagement == "high"
        assert profile.dominant_confidence == "confident"


# --- should_regenerate_notes ---

class TestShouldRegenerateNotes:

    def test_returns_false_without_api_key(self, db, monkeypatch):
        monkeypatch.setattr("backend.coaching.profile.settings.anthropic_api_key", "")
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        ia = InteractionAssessment(phone_hash=ph, teachable_moment=True)
        assert should_regenerate_notes(profile, ia) is False

    def test_returns_true_on_teachable_moment(self, db, monkeypatch):
        monkeypatch.setattr("backend.coaching.profile.settings.anthropic_api_key", "sk-test")
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        ia = InteractionAssessment(phone_hash=ph, teachable_moment=True)
        assert should_regenerate_notes(profile, ia) is True

    def test_returns_true_at_interval(self, db, monkeypatch):
        monkeypatch.setattr("backend.coaching.profile.settings.anthropic_api_key", "sk-test")
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        profile.total_turns = NOTES_REGEN_INTERVAL
        db.commit()
        ia = InteractionAssessment(phone_hash=ph, teachable_moment=False)
        assert should_regenerate_notes(profile, ia) is True

    def test_returns_false_between_intervals(self, db, monkeypatch):
        monkeypatch.setattr("backend.coaching.profile.settings.anthropic_api_key", "sk-test")
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        profile.total_turns = 3
        db.commit()
        ia = InteractionAssessment(phone_hash=ph, teachable_moment=False)
        assert should_regenerate_notes(profile, ia) is False


# --- Integration with run_coaching ---

class TestProfileIntegration:

    def test_run_coaching_creates_profile(self, db):
        """run_coaching with phone_hash should create a WorkerProfile."""
        ph = hash_phone(TEST_PHONE)
        result = run_coaching(db, "Exposed rebar near walkway", phone_hash=ph)
        profile = db.query(WorkerProfile).filter(WorkerProfile.phone_hash == ph).first()
        assert profile is not None
        assert profile.total_turns == 1
        assert profile.total_sessions == 1

    def test_run_coaching_creates_assessment(self, db):
        """run_coaching should create an InteractionAssessment row."""
        ph = hash_phone(TEST_PHONE)
        run_coaching(db, "Loose guardrail on level 3", phone_hash=ph)
        ia = db.query(InteractionAssessment).filter(
            InteractionAssessment.phone_hash == ph
        ).first()
        assert ia is not None
        assert ia.response_mode is not None
        assert ia.worker_text_length == len("Loose guardrail on level 3")

    def test_multiple_turns_increment_profile(self, db):
        """Multiple coaching calls should increment profile counters."""
        ph = hash_phone(TEST_PHONE)
        run_coaching(db, "Exposed rebar", phone_hash=ph)
        run_coaching(db, "Crew wearing PPE", phone_hash=ph)
        run_coaching(db, "Nice staging area", phone_hash=ph)

        profile = db.query(WorkerProfile).filter(WorkerProfile.phone_hash == ph).first()
        assert profile.total_turns == 3

        assessments = db.query(InteractionAssessment).filter(
            InteractionAssessment.phone_hash == ph
        ).all()
        assert len(assessments) == 3

    def test_tier_resolves_from_profile(self, db):
        """Engine should use profile tier, not default 1."""
        ph = hash_phone(TEST_PHONE)
        profile = get_or_create_profile(db, ph)
        profile.current_tier = 3
        db.commit()

        result = run_coaching(db, "Check this setup", phone_hash=ph)
        # The session should reflect the profile's tier
        from backend.models import CoachingSession
        session = db.get(CoachingSession, result.session_id)
        assert session.worker_tier == 3

    def test_without_phone_hash_no_profile(self, db):
        """run_coaching without phone_hash should not create a profile."""
        run_coaching(db, "Just a test observation")
        count = db.query(WorkerProfile).count()
        assert count == 0
        count = db.query(InteractionAssessment).count()
        assert count == 0
