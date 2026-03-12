"""Tests for backend.coaching.engine — mock mode, sessions, multi-turn, photos."""

import json

import pytest

from backend.coaching.engine import (
    CoachingResult,
    _classify_mock,
    _generate_mock_response,
    coach_mock,
    get_or_create_session,
    run_coaching,
)
from backend.models import CoachingResponse, CoachingSession, Observation, hash_phone
from tests.conftest import TEST_PHONE


# --- Mock classification tests ---

class TestMockClassification:

    def test_fall_hazard_classified_as_alert(self):
        cat, sev, mode, lang = _classify_mock("Worker near unprotected edge on the 3rd floor")
        assert cat == "environmental"
        assert sev >= 4
        assert mode == "alert"

    def test_rebar_classified_as_alert(self):
        cat, sev, mode, lang = _classify_mock("Exposed rebar near south entrance no caps")
        assert cat == "environmental"
        assert sev >= 4

    def test_electrical_classified_as_critical(self):
        cat, sev, mode, lang = _classify_mock("Electrocution risk from live wire near the trailer")
        assert cat == "equipment"
        assert sev == 5
        assert mode == "alert"

    def test_trench_classified_as_critical(self):
        cat, sev, mode, lang = _classify_mock("Deep trench with no shoring")
        assert sev == 5
        assert mode == "alert"

    def test_ppe_classified_as_validate(self):
        cat, sev, mode, lang = _classify_mock("Crew wearing hard hats and vests today")
        assert cat == "procedural"
        assert mode == "validate"

    def test_housekeeping_classified_as_nudge(self):
        cat, sev, mode, lang = _classify_mock("Lots of debris and clutter around the work area")
        assert mode == "nudge"

    def test_positive_behavior_classified_as_affirm(self):
        cat, sev, mode, lang = _classify_mock("Great job by the crew keeping the area safe today")
        assert mode == "affirm"

    def test_generic_observation_defaults_to_probe(self):
        cat, sev, mode, lang = _classify_mock("Something off about the setup at zone C")
        assert mode == "probe"

    def test_spanish_detection(self):
        cat, sev, mode, lang = _classify_mock("Hay peligro de caida en el andamio")
        assert lang == "es"

    def test_english_default(self):
        cat, sev, mode, lang = _classify_mock("Exposed rebar near the walkway")
        assert lang == "en"


# --- Mock response generation (framework-compliant) ---

class TestMockResponses:

    def test_alert_response_is_direct_and_urgent(self):
        resp = _generate_mock_response("alert")
        # Alert should be a direct statement, not a question
        assert len(resp) > 20
        assert len(resp) <= 320

    def test_validate_response_invites_reply(self):
        resp = _generate_mock_response("validate")
        # Validate should ask what they plan to do
        assert "?" in resp

    def test_nudge_asks_question(self):
        resp = _generate_mock_response("nudge")
        assert "?" in resp

    def test_probe_asks_for_context(self):
        resp = _generate_mock_response("probe")
        assert "?" in resp

    def test_affirm_is_specific(self):
        resp = _generate_mock_response("affirm")
        # Should not contain generic corporate praise
        assert "Great job!" not in resp
        assert "Safety as a Contact" not in resp

    def test_no_responses_contain_prohibited_language(self):
        """No mock response should violate the framework."""
        prohibited = ["OSHA", "Safety as a Contact", "You should", "Be careful",
                       "Safety first", "Remember to", "Best practice", "I noticed"]
        for mode in ["alert", "validate", "nudge", "probe", "affirm"]:
            resp = _generate_mock_response(mode)
            for phrase in prohibited:
                assert phrase not in resp, f"'{phrase}' found in {mode} response: {resp}"

    def test_photo_responses_differ_from_text(self):
        text_resp = _generate_mock_response("probe", has_photo=False)
        photo_resp = _generate_mock_response("probe", has_photo=True)
        # They should be different (photo-specific vs text-specific)
        assert text_resp != photo_resp


# --- coach_mock integration ---

class TestCoachMock:

    def test_returns_coaching_result(self):
        result = coach_mock("Exposed rebar near the walkway")
        assert isinstance(result, CoachingResult)
        assert result.is_mock is True
        assert result.model_used == "mock"

    def test_all_fields_populated(self):
        result = coach_mock("Worker on ladder without harness")
        assert result.response_text
        assert result.response_mode in ("alert", "validate", "nudge", "probe", "affirm")
        assert result.hazard_category in ("environmental", "equipment", "procedural", "ergonomic", "behavioral")
        assert 1 <= result.severity <= 5
        assert result.language in ("en", "es")
        assert result.latency_ms >= 0

    def test_severity_5_forces_alert(self):
        result = coach_mock("Electrocution risk from live wire near the work area")
        assert result.severity == 5
        assert result.response_mode == "alert"

    def test_trade_parameter_accepted(self):
        result = coach_mock("Unsafe scaffold", trade="scaffold_builder")
        assert isinstance(result, CoachingResult)

    def test_experience_parameter_accepted(self):
        result = coach_mock("Trip hazard", experience_level="expert")
        assert isinstance(result, CoachingResult)

    def test_photo_flag_set(self):
        result = coach_mock("Check this out", media_urls=["https://example.com/photo.jpg"])
        assert result.has_photo is True

    def test_no_photo_flag_when_text_only(self):
        result = coach_mock("Just a text observation")
        assert result.has_photo is False

    def test_turn_number_passed_through(self):
        result = coach_mock("Follow up", turn_number=3)
        assert result.turn_number == 3


# --- Session management ---

class TestSessionManagement:

    def test_creates_new_session(self, db):
        ph = hash_phone(TEST_PHONE)
        session = get_or_create_session(db, ph)
        assert session.id is not None
        assert session.turn_count == 1
        assert session.is_closed is False

    def test_resumes_active_session(self, db):
        ph = hash_phone(TEST_PHONE)
        s1 = get_or_create_session(db, ph)
        s2 = get_or_create_session(db, ph)
        assert s1.id == s2.id
        assert s2.turn_count == 2  # incremented

    def test_new_session_after_timeout(self, db):
        """After session_timeout_minutes, a new session should be created."""
        from datetime import timedelta
        from backend.models import utcnow

        ph = hash_phone(TEST_PHONE)
        s1 = get_or_create_session(db, ph)

        # Simulate timeout by pushing last_activity_at back
        s1.last_activity_at = utcnow() - timedelta(minutes=300)
        db.commit()

        s2 = get_or_create_session(db, ph)
        assert s2.id != s1.id
        assert s2.turn_count == 1

        # Old session should be closed
        db.refresh(s1)
        assert s1.is_closed is True


# --- run_coaching with DB persistence ---

class TestRunCoaching:

    def test_creates_coaching_response_record(self, db):
        """run_coaching should persist a CoachingResponse row."""
        result = run_coaching(db, "Exposed rebar near walkway")
        assert result.is_mock is True

        cr = db.query(CoachingResponse).first()
        assert cr is not None
        assert cr.response_mode == result.response_mode
        assert cr.hazard_category == result.hazard_category

    def test_links_to_observation(self, db):
        """When observation_id is provided, it should link and update the observation."""
        obs = Observation(raw_text="Saw a trench with no shoring")
        db.add(obs)
        db.commit()
        db.refresh(obs)

        result = run_coaching(db, obs.raw_text, observation_id=obs.id)

        db.refresh(obs)
        assert obs.hazard_category is not None
        assert obs.severity is not None

        cr = db.query(CoachingResponse).filter(CoachingResponse.observation_id == obs.id).first()
        assert cr is not None

    def test_without_observation_id(self, db):
        """Should work fine without an observation_id."""
        result = run_coaching(db, "Everything looks safe today")
        cr = db.query(CoachingResponse).first()
        assert cr is not None
        assert cr.observation_id is None

    def test_response_text_under_320_chars(self, db):
        """Response should never exceed 2 SMS segments."""
        result = run_coaching(db, "Major fire near fuel storage")
        assert len(result.response_text) <= 320

    def test_creates_session_when_phone_hash_provided(self, db):
        """Should create a coaching session when phone_hash is given."""
        ph = hash_phone(TEST_PHONE)
        result = run_coaching(
            db, "Exposed rebar", phone_hash=ph,
        )
        assert result.session_id is not None

        session = db.get(CoachingSession, result.session_id)
        assert session is not None
        assert session.turn_count == 1

    def test_session_tracks_modes(self, db):
        """Session should track which response modes were used."""
        ph = hash_phone(TEST_PHONE)
        result = run_coaching(db, "Exposed rebar near walkway", phone_hash=ph)

        session = db.get(CoachingSession, result.session_id)
        modes = json.loads(session.response_modes_used)
        assert result.response_mode in modes

    def test_photo_observation_with_media_urls(self, db):
        """run_coaching should pass media_urls through."""
        urls = ["https://api.twilio.com/media/test.jpg"]
        result = run_coaching(
            db, "Check this", media_urls=urls, phone_hash=hash_phone(TEST_PHONE),
        )
        assert result.has_photo is True
