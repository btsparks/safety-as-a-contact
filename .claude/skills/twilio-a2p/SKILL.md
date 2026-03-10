---
name: twilio-a2p
description: Twilio A2P 10DLC registration and SMS compliance reference. Auto-invokes when working on SMS features, consent management, or message sending. Contains TCPA, CTIA, and carrier requirements.
allowed-tools: Read, Grep, Bash, Edit, Write
---

# Twilio A2P Compliance Skill

## A2P 10DLC Registration

**Brand Registration** (required before campaign)
- Legal business name: "Safety as a Contact"
- Website: safetyasacontact.com
- Business address, phone, registered agent
- Industry: Occupational Safety & Health
- Status must be VERIFIED before campaign launch

**Campaign Registration** (per messaging use case)
- Campaign name: SMS Coaching for Construction Workers
- Campaign description: Real-time AI safety coaching for construction site hazard identification
- Vertical: Workplace Safety
- Opt-in form type: SMS (double opt-in)
- Estimated volume: [Define based on worker count]
- Message sample: "You're in! Text us anytime you spot a hazard on the job. We'll coach you through it."

## TCPA Compliance (Critical)

- **Requirement**: Prior express written consent REQUIRED
- **Penalty**: $500–$1,500 per message violating consent
- **Sending window**: 8am–9pm recipient's local time ONLY
- **Consent scope**: Jan 2026 rule — One-to-one consent rule: Phone number can only be used for consent purpose given
- **Record keeping**: Consent records must include date, method, content worker agreed to

## CTIA Requirements

- **Non-sharing clause**: "Safety as a Contact will not share your phone number with third parties"
- **Sender identity**: Always include brand name in first message
- **Message frequency disclosure**: "Msg frequency varies" in initial consent message
- **SHAFT prohibited**: Cannot send Sexual, Harmful, Abusive, Fraudulent, Transactional without explicit opt-in
- **Short codes vs 10DLC**: Use 10DLC (our allocated number) for coaching, not shared short codes

## Double Opt-In Consent Flow

**Step 1: Worker initiates**
- Worker texts "Hi" or any message to Safety as a Contact number

**Step 2: System sends opt-in request**
```
Welcome to Safety as a Contact! We provide AI-powered safety
coaching via text. Msg frequency varies. Msg&data rates may apply.
Reply YES to opt in, STOP to cancel. Terms:
safetyasacontact.com/sms-terms
```

**Step 3: Worker confirms**
- Worker replies "YES" (or YES, yep, ok, confirm — case-insensitive)

**Step 4: System confirms enrollment**
```
You're in! Text us anytime you spot a hazard on the job.
We'll coach you through it. Reply STOP anytime to opt out.
- Safety as a Contact
```

## Consent Database Schema

```sql
CREATE TABLE consent_records (
  id UUID PRIMARY KEY,
  phone_number VARCHAR(20) UNIQUE,
  opted_in_at TIMESTAMP,
  opted_in_method ENUM('sms_double_optin', 'web_form', 'verbal_documented'),
  consent_message_sent VARCHAR(500),
  worker_response VARCHAR(10),
  ip_address VARCHAR(45),
  worker_trade VARCHAR(50),
  active BOOLEAN DEFAULT true,
  opted_out_at TIMESTAMP,
  opted_out_method VARCHAR(20),
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

## Opt-Out Handling

**Trigger words** (case-insensitive):
- STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT

**Required response** (within 1 second):
```
You've been unsubscribed from Safety as a Contact.
You won't receive more messages. Reply START to re-opt in.
```

**Database action**: Set active = false, opted_out_at = NOW(), opted_out_method = 'sms_stop'

## Message Template Compliance

Every outbound message must include:
1. Brand identity in first or last message of conversation
2. Opt-out instruction: "Reply STOP to cancel" OR "Text STOP to opt out"
3. No hidden phone numbers or redirect URLs (violates CTIA transparency)
4. No sender ID spoofing — use registered 10DLC number

**Non-compliance example**: "Coach: Great catch! [hidden link]" ← WRONG (no brand, no opt-out)

**Compliance example**: "You're right on the hazard chain here. Safety as a Contact coaching. Reply STOP to opt out."

## Pre-Submission Checklist

Website must include:
- [ ] Privacy Policy with SMS-specific section covering:
  - Data collection for SMS
  - Consent storage duration (3 years minimum)
  - Third-party sharing policy (none)
  - Compliance framework reference
- [ ] Terms of Service with SMS-specific terms page
- [ ] SMS-specific terms (safetyasacontact.com/sms-terms):
  - Message frequency ("varies based on observation")
  - Carrier data rates apply
  - Consent revocation process
  - No guarantee of response time
  - Trade-specific coaching disclaimer

## Common Rejection Reasons

| Rejection | Cause | Fix |
|-----------|-------|-----|
| Missing privacy policy | No SMS data handling docs | Add SMS section to privacy.md |
| Unclear opt-out | Doesn't mention STOP | Add "Reply STOP" to every template |
| Vague use case | "Safety coaching" too broad | "Real-time hazard coaching for construction workers" |
| No consent evidence | No double opt-in shown | Document exact consent flow |
| Frequency undefined | "As needed" doesn't work | "Varies: 0-10 daily during active shifts" |
| High-volume risk | Volume threshold exceeded | Adjust campaign volume estimate down |

## Carrier Filtering Zones

Carriers (Verizon, AT&T, T-Mobile) have separate filters. "Coaching" content may flag as spam unless:
- Consent records are pristine (no invalid numbers, no rapid re-opts)
- Message content matches use case (not marketing)
- Sender reputation stays high (monitor bounce rate, complaint rate)

Monitor Twilio dashboard for carrier feedback.
