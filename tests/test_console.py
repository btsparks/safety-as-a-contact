"""Tests for backend.api.console — test console API endpoints."""

import pytest

from backend.models import CoachingResponse, ConsentRecord, MessageLog, Observation, hash_phone
from backend.sms.consent import create_consent
from tests.conftest import TEST_PHONE, TEST_PHONE_2


class TestSimulate:

    def test_new_number_gets_consent_request(self, client, db):
        """First message from unknown number should trigger consent flow."""
        resp = client.post("/api/test/simulate", json={
            "phone": "+18015559999",
            "message": "Hello",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "consent_request"
        assert "opt in" in data["response_text"].lower() or "YES" in data["response_text"]

    def test_opt_in_flow(self, client, db):
        """YES after consent request should activate consent."""
        # First message triggers consent request
        client.post("/api/test/simulate", json={
            "phone": "+18015559999",
            "message": "Hello",
        })
        # Opt in
        resp = client.post("/api/test/simulate", json={
            "phone": "+18015559999",
            "message": "YES",
        })
        data = resp.json()
        assert data["action"] == "opt_in"

    def test_observation_returns_coaching(self, client, db, seed_consent):
        """Message from consented number should return coaching result."""
        resp = client.post("/api/test/simulate", json={
            "phone": TEST_PHONE,
            "message": "Exposed rebar near south entrance no caps",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "observation"
        assert "coaching_result" in data
        cr = data["coaching_result"]
        assert cr["response_mode"] in ("alert", "validate", "nudge", "probe", "affirm")
        assert cr["hazard_category"] is not None
        assert 1 <= cr["severity"] <= 5
        assert cr["is_mock"] is True

    def test_opt_out_flow(self, client, db, seed_consent):
        """STOP should revoke consent."""
        resp = client.post("/api/test/simulate", json={
            "phone": TEST_PHONE,
            "message": "STOP",
        })
        data = resp.json()
        assert data["action"] == "opt_out"


class TestConversations:

    def test_list_conversations_empty(self, client, db):
        resp = client.get("/api/test/conversations")
        assert resp.status_code == 200
        assert resp.json()["conversations"] == []

    def test_list_conversations_after_messages(self, client, db, seed_consent):
        """After sending messages, conversations should appear."""
        client.post("/api/test/simulate", json={
            "phone": TEST_PHONE,
            "message": "Trip hazard in the hallway",
        })
        resp = client.get("/api/test/conversations")
        data = resp.json()
        assert len(data["conversations"]) > 0
        assert data["conversations"][0]["message_count"] >= 1  # at least inbound logged

    def test_get_conversation_by_phone(self, client, db, seed_consent):
        """Should return message history for a phone number."""
        client.post("/api/test/simulate", json={
            "phone": TEST_PHONE,
            "message": "Ladder not secured properly",
        })
        resp = client.get(f"/api/test/conversation/{TEST_PHONE}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) >= 1  # at least inbound logged


class TestStats:

    def test_stats_empty(self, client, db):
        resp = client.get("/api/test/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_messages"] == 0
        assert data["total_observations"] == 0

    def test_stats_after_coaching(self, client, db, seed_consent):
        """Stats should reflect coaching activity."""
        client.post("/api/test/simulate", json={
            "phone": TEST_PHONE,
            "message": "Saw exposed rebar near the walkway",
        })
        resp = client.get("/api/test/stats")
        data = resp.json()
        assert data["total_observations"] >= 1
        assert data["total_coaching_responses"] >= 1
        assert data["total_messages"] >= 1  # outbound may be blocked by sending window


class TestReset:

    def test_reset_clears_data(self, client, db, seed_consent):
        """Reset should clear all test data."""
        # Create some data
        client.post("/api/test/simulate", json={
            "phone": TEST_PHONE,
            "message": "Test observation",
        })

        # Reset
        resp = client.delete("/api/test/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"]["message_log"] >= 1

        # Verify empty
        stats = client.get("/api/test/stats").json()
        assert stats["total_messages"] == 0


class TestFullConsoleFlow:
    """End-to-end test matching the verification curl commands from the plan."""

    def test_consent_then_observe_then_stats(self, client, db):
        phone = "+18015559999"

        # 1. New number → consent request
        r1 = client.post("/api/test/simulate", json={"phone": phone, "message": "Hello"})
        assert r1.json()["action"] == "consent_request"

        # 2. Opt in
        r2 = client.post("/api/test/simulate", json={"phone": phone, "message": "YES"})
        assert r2.json()["action"] == "opt_in"

        # 3. Send observation → coaching response
        r3 = client.post("/api/test/simulate", json={
            "phone": phone,
            "message": "Exposed rebar near south entrance no caps",
        })
        d3 = r3.json()
        assert d3["action"] == "observation"
        assert "coaching_result" in d3
        assert d3["coaching_result"]["response_mode"] in ("alert", "validate", "nudge", "probe", "affirm")

        # 4. Check stats
        r4 = client.get("/api/test/stats")
        d4 = r4.json()
        assert d4["total_observations"] >= 1
        assert d4["total_coaching_responses"] >= 1
        assert d4["total_messages"] >= 4  # 3 inbound + multiple outbound
