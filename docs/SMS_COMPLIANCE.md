# SMS Compliance Reference for Developers

**Purpose:** Quick developer reference for SMS compliance during implementation
**Scope:** Code-level compliance checks, not legal guidance
**Last Updated:** 2026-03-10

---

## Quick Compliance Checklist

Before sending ANY SMS message, verify:

- [ ] Recipient has active consent in `consent_records` table
- [ ] Current time falls within sending window (8am-9pm recipient's local timezone)
- [ ] Message text includes opt-out language OR consent header
- [ ] Message stays within 160-character SMS limit (or multi-part SMS handling)
- [ ] Recipient has not opted out (is_active=True in consent_records)
- [ ] Rate limit not exceeded (max messages per phone number per day)
- [ ] Message logged to `message_log` table before sending
- [ ] No PII in message (use worker_id, not full name or SSN)

**If ANY check fails:** DO NOT SEND. Log error and route to error handler.

---

## Consent Verification Flow (Code-Level)

### Database Schema
```sql
CREATE TABLE consent_records (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    company_id INT NOT NULL,
    worker_id INT,
    consent_type VARCHAR(50),  -- 'sms_coaching', 'sms_nudge', 'sms_alert'
    is_active BOOLEAN DEFAULT TRUE,
    date_consented TIMESTAMP,
    date_optout TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_consent_phone ON consent_records(phone_number);
CREATE INDEX idx_consent_company ON consent_records(company_id);
```

### Verification Function
```python
def verify_consent(phone_number: str, message_type: str) -> bool:
    """
    Verify recipient has active consent before sending.

    Args:
        phone_number: E.164 format (+1234567890)
        message_type: 'coaching', 'nudge', 'alert', 'toolbox_talk'

    Returns:
        True if consent is active and valid, False otherwise
    """
    consent = db.session.query(ConsentRecord).filter(
        ConsentRecord.phone_number == phone_number,
        ConsentRecord.consent_type == message_type,
        ConsentRecord.is_active == True
    ).first()

    return consent is not None
```

### Consent Verification Rules
- **Active Consent Required:** `is_active=True` in database
- **Consent Type Match:** Message type must match consent_type (if coaching message, check 'sms_coaching' consent)
- **No Expired Consent:** Even if is_active=True, check consent_date is not older than 18 months (re-consent recommended annually)
- **Opt-Out Honored:** If date_optout is not NULL, do NOT send

---

## Opt-Out Keywords & Processing

### Required Opt-Out Keywords (STOP, CANCEL, END, QUIT, UNSUBSCRIBE)
Process these keywords immediately upon receipt, case-insensitive:

- STOP
- CANCEL
- END
- QUIT
- UNSUBSCRIBE

### Opt-Out Workflow
```python
def handle_opt_out(phone_number: str):
    """
    Process opt-out immediately.
    Update consent_records and send confirmation.
    """
    consent = db.session.query(ConsentRecord).filter(
        ConsentRecord.phone_number == phone_number
    ).all()

    for record in consent:
        record.is_active = False
        record.date_optout = datetime.now()

    db.session.commit()

    # Send opt-out confirmation
    response_msg = (
        "You've been unsubscribed from Safety as a Contact. "
        "You will not receive any more messages. "
        "Text START to re-subscribe."
    )
    send_sms(phone_number, response_msg, skip_consent_check=True)
```

### Opt-Out Response Template
**Exact wording (required by TCPA):**
```
You've been unsubscribed from Safety as a Contact.
You will not receive any more messages.
Text START to re-subscribe.
```

**Length:** 160 characters (fits in single SMS)

---

## Sending Window Enforcement

### Rule
Do not send messages outside 8:00 AM - 9:00 PM in recipient's local timezone.

### Implementation
```python
from datetime import datetime
import pytz

def is_within_sending_window(phone_number: str) -> bool:
    """
    Check if current time is within sending window for recipient.
    Default to UTC-5 (Eastern) if timezone unknown.
    """
    # Lookup recipient timezone from worker profile or default
    worker = db.session.query(Worker).filter(
        Worker.phone_number == phone_number
    ).first()

    tz_name = worker.timezone or 'America/New_York'
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)

    # Allow 8am - 9pm
    return 8 <= now.hour < 21
```

### Sending Window Rules
- **Start Time:** 8:00 AM local timezone (send at or after 8:00)
- **End Time:** 9:00 PM local timezone (do not send at or after 21:00)
- **Weekends/Holidays:** Same window applies (no exception)
- **Daylight Saving Time:** Respect local DST rules (use pytz)

---

## Message Template Requirements

### Every Outbound Message Must Include

1. **Brand Identity**
   - Sender name: "Safety Coach" (Twilio Messaging Service name)
   - Start with greeting or context (not just raw text)

2. **Opt-Out Language**
   - For messages under 160 characters: Include full opt-out footer
   - For longer messages: Include opt-out reference

### Template Examples

**Coaching Response (primary use case):**
```
Safety Coach: Great observation about [hazard]. Here's how to handle it: [coaching].
Text STOP to opt-out.
```
(Adjust length to stay under 160 or use multi-part SMS)

**Confirmation Message:**
```
Your observation was used in today's safety briefing. Keep it up!
Reply STOP to opt-out.
```

**Toolbox Talk Invite:**
```
Morning shift check-in from Safety Coach: We're discussing [hazard category] today.
Join the briefing at 8:15am. Text STOP to opt-out.
```

### Multi-Part SMS Handling
- If message exceeds 160 characters, Twilio splits into multiple SMS (counts as 2+ messages)
- Update rate limiting logic to account for multi-part messages
- Max recommended length: 320 characters (fits in 2 SMS)
- Opt-out footer can be in final message segment

---

## Rate Limiting

### Rule
Maximum of 5 messages per phone number per calendar day (8am-9pm window).

### Implementation
```python
def check_rate_limit(phone_number: str, max_per_day: int = 5) -> bool:
    """
    Verify message count for recipient today.
    """
    today = datetime.now().date()
    message_count = db.session.query(MessageLog).filter(
        MessageLog.to_phone == phone_number,
        MessageLog.sent_date == today,
        MessageLog.status == 'sent'
    ).count()

    return message_count < max_per_day
```

### Rate Limit Rules
- **Count:** Messages sent successfully (status='sent')
- **Period:** Calendar day (midnight to midnight in recipient timezone)
- **Include:** All message types (coaching, nudge, alert, confirmation)
- **Exclude:** Opt-out confirmations and system errors
- **Enforcement:** Reject new message if limit exceeded; log and notify admin

---

## Consent Record Schema & Retention

### Consent Record Fields
```python
class ConsentRecord(Base):
    __tablename__ = 'consent_records'

    id = Column(Integer, primary_key=True)
    phone_number = Column(String(20), nullable=False, index=True)  # E.164
    company_id = Column(Integer, nullable=False, index=True)
    worker_id = Column(Integer)
    consent_type = Column(String(50))  # 'sms_coaching', 'sms_nudge', etc.
    is_active = Column(Boolean, default=True)
    date_consented = Column(DateTime, nullable=False)
    date_optout = Column(DateTime)
    consented_via = Column(String(50))  # 'web_form', 'sms_keyword', 'admin'
    ip_address = Column(String(45))  # For audit trail (IPv4 or IPv6)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

### Retention Rules
- **Retention Period:** 5 years minimum (TCPA and FCC requirement)
- **Active Records:** Keep forever for active workers
- **Inactive Records:** Keep for 5 years after opt-out date
- **Audit Trail:** Never delete date_optout or consented_via (immutable)
- **Data Purge Job:** Run quarterly to expire old inactive records (log before delete)

### Consent Logging
Every consent change must be logged:
```python
def log_consent_change(phone_number: str, action: str, reason: str):
    """
    Log consent state change for audit trail.
    """
    log = ConsentLog(
        phone_number=phone_number,
        action=action,  # 'opted_in', 'opted_out', 'reactivated'
        reason=reason,
        timestamp=datetime.now()
    )
    db.session.add(log)
    db.session.commit()
```

---

## TCPA Penalties & Risk Summary

### Potential Penalties
- **Per Message Violation:** $500 - $1,500 per message
- **Cumulative Risk:** 1,000 messages at $1,000/message = $1,000,000 liability
- **Class Action Exposure:** TCPA allows class action litigation

### High-Risk Violations
1. Sending to number without active consent → $1,500 per message
2. Ignoring opt-out request → $1,500 per message sent after opt-out
3. Sending outside permitted hours → $1,500 per message
4. Sending via automated dialer without consent → $1,500 per message
5. No opt-out option in message → $500+ per message

### Compliance = Risk Mitigation
- Verify consent before EVERY send
- Log EVERY transaction
- Honor opt-out IMMEDIATELY
- Respect sending windows
- Include opt-out language ALWAYS

---

## Website Pages Required for Campaign Approval

Twilio A2P campaign registration requires these pages live at production URL:

### 1. Privacy Policy
**Must include:**
- What data is collected (phone, hazard observations, company affiliation)
- How data is used (coaching, toolbox talks, engagement metrics)
- Data sharing statement: "We do not sell or share your data with third parties" (CTIA compliance)
- Data retention: "SMS consent records retained for 5 years per FCC requirements"
- Opt-out process: "Text STOP to unsubscribe from all messages"
- Contact: Privacy contact email and mailing address
- Update history: Date last updated

### 2. Terms of Service
**Must include:**
- User obligations (accurate information, lawful use)
- Service restrictions (no harassment, no illegal activity)
- Limitation of liability (Safety as a Contact not liable for hazards)
- SMS terms reference (link to SMS_TERMS page)
- Dispute resolution (arbitration or court jurisdiction)
- Age requirement (18+ or workers in lawful employment)

### 3. SMS Terms & Conditions
**Must include:**
- Opt-in confirmation: "By texting keyword or submitting form, you consent to SMS messages"
- Opt-out keywords: List STOP, CANCEL, END, QUIT, UNSUBSCRIBE
- Message frequency: "Up to 5 messages per day during business hours"
- Carrier charges: "Message and data rates may apply per your carrier"
- Support: "Text HELP for support or email [support email]"
- Expected use: "Messages are safety coaching and workplace notifications"

### 4. Landing Page
**Must include:**
- Clear service description
- Link to Privacy Policy
- Link to Terms of Service
- Link to SMS Terms
- CTA for consent (web form as backup)

**Production URL:** safetyasacontact.com (or custom domain, no IP addresses)

---

## Privacy Policy - SMS-Specific Section Template

```markdown
## SMS Communications

Safety as a Contact sends SMS messages to provide workplace safety coaching,
observations, and daily toolbox talks.

**Data Collected:** Phone number, name (optional), company affiliation,
safety observations, message engagement.

**How It's Used:** To deliver targeted safety coaching, generate toolbox talks,
and track engagement metrics.

**Data Sharing:** We do not sell, rent, or share your personal data with
third parties. Data is shared only with your employer (company admin) for
safety program management.

**Retention:** SMS consent records are retained for 5 years per FCC regulations.
Observations are retained per company data retention policy.

**Opt-Out:** Text STOP to unsubscribe from all messages. You will receive
confirmation. Standard carrier rates apply.

**Support:** Text HELP or email safety@company.com for assistance.
```

---

## Developer Checklist Before Sending First SMS

- [ ] Consent verification function tested and working
- [ ] Opt-out keyword handler implemented and tested
- [ ] Sending window enforcement implemented
- [ ] Rate limiting implemented
- [ ] Message templates include opt-out language
- [ ] Message logging to message_log table working
- [ ] Twilio webhook integrated and receiving inbound SMS
- [ ] Error handling: what happens if send fails?
- [ ] Compliance checks before every send_sms() call
- [ ] Production secrets in environment variables, not code
- [ ] Test with Twilio sandbox first (no real SMS)
- [ ] Get legal review before sending to real numbers

---

## Testing Checklist

```python
# Test 1: Consent verification works
def test_verify_consent():
    create_consent_record(phone="+1234567890", is_active=True)
    assert verify_consent("+1234567890", "coaching") == True

    deactivate_consent("+1234567890")
    assert verify_consent("+1234567890", "coaching") == False

# Test 2: Opt-out keyword processing
def test_opt_out_processing():
    handle_inbound_sms("+1234567890", "STOP")
    assert verify_consent("+1234567890", "coaching") == False

# Test 3: Sending window enforcement
def test_sending_window():
    # Test at 7:59am - should block
    assert is_within_sending_window("+1234567890") == False  # (mocked time)

    # Test at 8:00am - should allow
    assert is_within_sending_window("+1234567890") == True   # (mocked time)

    # Test at 9:00pm - should block
    assert is_within_sending_window("+1234567890") == False  # (mocked time)

# Test 4: Rate limiting
def test_rate_limiting():
    send_sms("+1234567890", "msg 1")
    send_sms("+1234567890", "msg 2")
    send_sms("+1234567890", "msg 3")
    send_sms("+1234567890", "msg 4")
    send_sms("+1234567890", "msg 5")

    # 6th message should be rejected
    assert check_rate_limit("+1234567890") == False
```

---

## Common Compliance Mistakes to Avoid

| Mistake | Why It's Bad | Fix |
|---------|------------|-----|
| Sending to all workers without checking consent | TCPA violation ($1,500/msg) | Call verify_consent() before send |
| Ignoring STOP keyword | Continued harassment ($1,500/msg) | Process opt-out immediately |
| Sending at 7:45am | Outside permitted window ($1,500/msg) | Enforce 8am-9pm window |
| Message with no opt-out language | Compliance failure | Add "Text STOP to opt-out" to every message |
| Sending 10 messages in one day | Rate limit violation | Check rate_limit() before send |
| Deleting consent records after 1 year | Audit trail destruction | Keep for 5 years minimum |
| No error logging for failed sends | No accountability | Log all send attempts and failures |
| Using shortened URLs without disclosure | Deceptive practice | Use full URLs or very clear messaging |

---

## Key Numbers to Remember

- **8am to 9pm** — Sending window (recipient's local time)
- **5 messages/day** — Rate limit per phone number
- **160 characters** — Single SMS limit (multi-part after that)
- **5 years** — Consent record retention minimum
- **$500-$1,500** — TCPA penalty per message violation
- **E.164 format** — Phone number format in database (+1234567890)
- **0.7 seconds** — Target response time for coaching engine

---

## Questions or Concerns?

Before implementing any SMS feature, verify against this document.
If compliance question arises, check `BEHAVIORAL_FRAMEWORK.md` or escalate to legal review.

**No SMS sent without consent. No exceptions.**
