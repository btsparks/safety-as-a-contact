"""End-to-end integration tests — full SMS flows."""

from backend.models import ConsentRecord, MessageLog, hash_phone
from tests.conftest import TEST_PHONE


def test_full_optin_flow(client, db):
    """New number → consent request → YES → confirmed → observation → ack."""
    phone = "+18015559999"
    ph = hash_phone(phone)

    # Step 1: New number texts in
    resp = client.post("/api/sms/inbound", data={
        "From": phone, "Body": "Hi there", "MessageSid": "SM_int_001",
    })
    assert resp.status_code == 200

    # Should have pending consent + outbound consent request
    cr = db.query(ConsentRecord).filter(ConsentRecord.phone_hash == ph).first()
    assert cr is not None
    assert cr.is_active is False

    # Step 2: Worker replies YES
    resp = client.post("/api/sms/inbound", data={
        "From": phone, "Body": "YES", "MessageSid": "SM_int_002",
    })
    assert resp.status_code == 200

    # Consent should now be active
    db.refresh(cr)
    assert cr.is_active is True

    # Step 3: Worker sends an observation
    resp = client.post("/api/sms/inbound", data={
        "From": phone, "Body": "Scaffolding missing guardrails on level 3",
        "MessageSid": "SM_int_003",
    })
    assert resp.status_code == 200

    # Observation should be logged
    obs_log = db.query(MessageLog).filter(
        MessageLog.phone_hash == ph,
        MessageLog.message_type == "observation",
    ).first()
    assert obs_log is not None


def test_full_optout_flow(client, db):
    """Consented number → STOP → revoked → new message → re-consent flow."""
    phone = "+18015558888"
    ph = hash_phone(phone)

    # Pre-consent the phone
    cr = ConsentRecord(
        phone_hash=ph,
        consent_type="sms_coaching",
        consent_method="sms_double_optin",
        is_active=True,
    )
    db.add(cr)
    db.commit()

    # Step 1: Worker opts out
    resp = client.post("/api/sms/inbound", data={
        "From": phone, "Body": "STOP", "MessageSid": "SM_int_004",
    })
    assert resp.status_code == 200

    db.refresh(cr)
    assert cr.is_active is False
    assert cr.revoked_at is not None

    # Step 2: Worker texts again — should get new consent request
    resp = client.post("/api/sms/inbound", data={
        "From": phone, "Body": "Hey I want back in", "MessageSid": "SM_int_005",
    })
    assert resp.status_code == 200

    # Step 3: Worker says START
    resp = client.post("/api/sms/inbound", data={
        "From": phone, "Body": "start", "MessageSid": "SM_int_006",
    })
    assert resp.status_code == 200

    db.refresh(cr)
    assert cr.is_active is True


def test_opt_out_case_insensitive(client, db):
    """All opt-out keyword variations should work."""
    for keyword in ["STOP", "stop", "Cancel", "END", "quit", "UNSUBSCRIBE"]:
        phone = f"+1801555{hash(keyword) % 10000:04d}"
        ph = hash_phone(phone)

        # Pre-consent
        cr = ConsentRecord(
            phone_hash=ph,
            consent_type="sms_coaching",
            consent_method="sms_double_optin",
            is_active=True,
        )
        db.add(cr)
        db.commit()

        resp = client.post("/api/sms/inbound", data={
            "From": phone, "Body": keyword, "MessageSid": f"SM_kw_{keyword}",
        })
        assert resp.status_code == 200

        db.refresh(cr)
        assert cr.is_active is False, f"Keyword '{keyword}' should have revoked consent"


def test_message_log_audit_trail(client, db):
    """Every interaction should leave a message_log entry."""
    phone = "+18015557777"
    ph = hash_phone(phone)

    # 3 interactions: new contact, YES, observation
    client.post("/api/sms/inbound", data={"From": phone, "Body": "hi", "MessageSid": "SM_a1"})
    client.post("/api/sms/inbound", data={"From": phone, "Body": "YES", "MessageSid": "SM_a2"})
    client.post("/api/sms/inbound", data={"From": phone, "Body": "No hard hat zone B", "MessageSid": "SM_a3"})

    logs = db.query(MessageLog).filter(MessageLog.phone_hash == ph).all()
    # 3 inbound guaranteed; outbound may be blocked by sending window
    inbound_count = sum(1 for l in logs if l.direction == "inbound")
    assert inbound_count >= 3
    assert len(logs) >= 3  # at minimum the 3 inbound messages
