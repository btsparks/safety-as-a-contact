# Safety as a Contact — Phase 3 Status & Alignment Check

**Date:** March 12, 2026
**Author:** Claude Code
**Purpose:** Honest assessment of what's built, what's wrong, and what needs to happen next

---

## What We Built (The Infrastructure)

Phase 2-3 infrastructure is solid. 94 tests passing, 85% coverage. The plumbing works.

### Backend (Complete)

| Component | File | What It Does | Status |
|-----------|------|-------------|--------|
| FastAPI app | `main.py` | Routes, startup, template serving | Done |
| Config | `config.py` | Environment variables, Twilio/Anthropic keys | Done |
| Database | `database.py` | SQLAlchemy engine, SQLite dev / PostgreSQL prod | Done |
| Models | `models.py` | 7 tables: Company, Project, Worker, ConsentRecord, Observation, CoachingResponse, MessageLog | Done |
| SMS Handler | `sms/handler.py` | Twilio webhook, message routing, `handle_inbound_message()` shared between webhook and console | Done |
| SMS Sender | `sms/sender.py` | Outbound SMS with consent + window + rate limit checks | Done |
| Consent | `sms/consent.py` | Double opt-in, opt-out, TCPA-compliant consent management | Done |
| Compliance | `sms/compliance.py` | Sending window (8am-9pm), rate limiting (5/day) | Done |
| Health | `api/health.py` | `GET /health` with DB connectivity check | Done |
| Console API | `api/console.py` | Simulate, conversations, stats, reset endpoints (dev-only) | Done |
| Console UI | `templates/console.html` | Chat-style SMS simulator with metadata panel | Done |
| Trades | `coaching/trades.py` | 12 construction trades with hazard profiles, fuzzy matching | Done |
| Logging | `logging_config.py` | JSON (prod) / readable (dev) structured logging | Done |

### Test Suite (94 Tests Passing)

| File | Tests | Coverage |
|------|-------|----------|
| `test_coaching_engine.py` | 24 | Mock classification, response generation, DB persistence |
| `test_console.py` | 11 | Full console flow: consent → observe → stats |
| `test_trades.py` | 11 | All 12 trades, fuzzy matching, aliases, defaults |
| `test_sms_handler.py` | 5 | Webhook routing: opt-out, opt-in, observation, empty |
| `test_compliance.py` | 10 | Sending window, rate limits, validation |
| `test_consent.py` | 8 | Create, verify, revoke, reactivate consent |
| `test_models.py` | 9 | All model creation, phone hashing |
| `test_database.py` | 2 | Table creation, health check |
| `test_integration.py` | 4 | Full opt-in/opt-out flows |
| Other | 10 | Config, health, sender |

### SMS Compliance (Complete)

- Double opt-in consent flow
- Immediate opt-out processing (STOP, CANCEL, END, QUIT, UNSUBSCRIBE, STOPALL)
- Sending window enforcement (8am-9pm)
- Rate limiting (5 messages/phone/day)
- Consent audit trail with soft deletes (5-year retention)
- All messages logged to `message_log` table
- Phone numbers stored as SHA256 hashes only

---

## What's Wrong (The Critical Gap)

The infrastructure works, but the brain — the coaching engine and interaction model — does not reflect the actual product vision. Here's the gap:

### 1. No Photo Support

**This is the primary use case.** A worker sees something on the job, takes a photo, and texts it. They may not know what the hazard is. They're asking for help.

**Current state:** The system only processes text. There is zero support for:
- Receiving MMS photos (Twilio sends `NumMedia`, `MediaUrl0`, `MediaContentType0`)
- Storing media URLs on Observation records
- Passing images to Claude Vision for analysis
- Simulating photo submissions in the test console

**What Twilio sends when a worker texts a photo:**
```
From: +18015551234
Body: "this doesn't look right"
NumMedia: 1
MediaUrl0: https://api.twilio.com/2010-04-01/.../Media/ME...
MediaContentType0: image/jpeg
```

### 2. The System Prompt Is Wrong

Our `coaching/prompts.py` reads like a corporate safety training module. It violates almost every rule in the SafetyTAP Response Framework — which is the proven, tested interaction model.

**What our prompt says:**
```
"You are a behavioral safety coach for construction workers..."
"Include OSHA reference only for severity 4-5"
"Sign off: - Safety as a Contact"
```

**What the SafetyTAP framework says:**
```
"You are a sharp, experienced construction coworker..."
"Never cite OSHA, regulations, company policy, or standards"
"Never say 'I' or reference yourself as an AI"
```

**Key differences:**

| Our Prompt | SafetyTAP Framework |
|-----------|-------------------|
| "Behavioral safety coach" identity | Experienced coworker / peer identity |
| OSHA citations encouraged | OSHA citations explicitly prohibited |
| "Safety as a Contact" sign-off | No brand identity in responses |
| Imperative language ("Flag it, secure the area") | Question-first ("What's your plan for...?") |
| Multiple observations per response | ONE observation per response, always |
| Template-driven mock responses | Specific, photo-referenced responses |
| Text analysis only | Vision-first analysis |

### 3. The Mock Responses Violate the Framework

Our mock mode returns responses like:
> "Heads up — that's a serious hazard. Environmental hazards like that need immediate controls. Flag it, secure the area, and make sure your crew knows. Good catch. - Safety as a Contact"

The SafetyTAP framework explicitly prohibits this pattern (called "The Safety Audit" anti-pattern):
- Stacks multiple instructions
- Uses corporate language ("immediate controls")
- Generic — applies to any observation
- Brand sign-off breaks peer voice
- No question, no specificity, no photo reference

**What it should sound like** (from SafetyTAP examples):
> "That wall is showing tension cracks. Get everyone back from the edge now. Don't go back in until that's shored or sloped."

Or for a nudge:
> "Pour setup looks dialed in. What's the plan for those cords if that area takes on more water?"

### 4. The Interaction Model Is Backwards

**What we built:** Worker describes a hazard in text → system classifies it → system confirms their observation.

**What the product actually is:** Worker sends a photo of their work area → AI identifies something they may not have noticed → AI helps them develop their OWN hazard recognition through questions.

The worker is not calling out hazards. The worker is asking for help seeing what they don't know they're missing. The AI is the experienced coworker who's been around long enough to spot the non-obvious thing.

---

## The SafetyTAP Response Framework (Source of Truth)

**Location:** `C:\Users\Travis Sparks\Desktop\AI Applications\SafetyTAP\RESPONSE_FRAMEWORK.md`

This document IS the product. Everything below comes directly from it.

### The Voice

SafetyTAP speaks like a sharp, experienced construction coworker who respects the person on the other end. Not a safety manager. Not a compliance officer. Not a training module. Not an AI. A peer.

- **Direct.** No hedging, no corporate softeners.
- **Brief.** Three lines max. If it needs scrolling on a phone, cut it.
- **Practical.** Actionable within 60 seconds.
- **Respectful of competence.** Never assume the worker doesn't know something.

### Five Response Modes (Priority Order)

```
ALERT > VALIDATE > NUDGE > PROBE > AFFIRM
```

**ALERT** — Imminent serious risk to life. State condition, consequence, action. No questions. Rare — overuse destroys trust.

**VALIDATE** — Worker expressed doubt or uncertainty. Affirm instinct FIRST ("trust that"), then give ONE specific reason why they're right. Most psychologically powerful mode.

**NUDGE** — Genuine hazard present but not life-threatening. Lead with something good, then ask a question. NEVER state hazard AND solution together — that skips the thinking.

**PROBE** — No obvious hazard, but worker's focus is narrow. Ask ONE question that expands awareness: overhead activity, weather, adjacent work, what happens later.

**AFFIRM** — Clean setup, solid work. Name exactly what they're doing right. Specific — not "looks good."

### Decision Tree

1. Could someone die or be seriously injured if work continues? → ALERT
2. Is the worker expressing doubt or asking "is this okay?" → VALIDATE
3. Is there a non-critical but genuine hazard? → NUDGE
4. Is there context to expand awareness? → PROBE
5. Default → AFFIRM

### Universal Rules (Non-Negotiable)

1. **Brevity:** 3 lines max, 40-60 words. No scrolling.
2. **Question-first:** Default format is a question (3:1 ratio to statements).
3. **Specificity:** Reference something specific in the photo/message. No generic advice.
4. **No stacking:** ONE hazard per response. Never list multiple.
5. **No citations:** Never reference OSHA, regulations, policy, or jargon.
6. **60-second rule:** Actionable within 60 seconds of reading.
7. **Positive ratio:** 2:1 positive (AFFIRM/VALIDATE) to corrective (NUDGE/ALERT) over time.
8. **No AI identity:** Never say "I," "based on the image," or reveal AI nature.

### Prohibited Language

Never use: "You should," "Be careful," "OSHA requires," "Safety first," "Great job!," "Remember to," "Important to note," "Best practice," "Ensure that," "I noticed that," "It appears that."

### Anti-Patterns (Explicitly Prohibited)

- **The Safety Audit:** Listing multiple hazards like an inspection report
- **The Textbook:** Background info + regulation citations
- **The Cheerleader:** "Great job keeping a clean workspace!"
- **The Anxious Parent:** "Please be very careful with that saw"
- **The Disclaimer:** "Based on what I can see, it appears there may be..."
- **The Robot:** "HAZARD IDENTIFIED: Fall protection required..."

---

## What Needs to Happen Next

### Priority 1: Rebuild the Coaching Engine Around SafetyTAP's Framework

**Files to rewrite:**
- `coaching/prompts.py` — Replace corporate system prompt with SafetyTAP's proven prompt, adapted for SMS delivery
- `coaching/engine.py` — Replace mock responses with framework-compliant templates; integrate Claude Vision for photo analysis
- `sms/handler.py` — Extract MMS media URLs from Twilio webhook (`NumMedia`, `MediaUrl0..N`)

**Files to modify:**
- `models.py` — Add `media_urls` (JSON) field to Observation model
- `api/console.py` — Add image URL input to simulate endpoint
- `templates/console.html` — Add photo upload/URL field to test console

### Priority 2: Photo Support End-to-End

The pipeline should be:

```
Worker texts photo + optional text
    ↓
Twilio webhook delivers MediaUrl0 + Body
    ↓
Handler extracts media URLs, creates Observation with media
    ↓
Coaching engine passes image(s) + text to Claude Vision
    ↓
Claude analyzes photo using SafetyTAP system prompt
    ↓
Response follows the 5-mode framework
    ↓
SMS sent back to worker (160-char target)
```

**Mock mode with photos:** When no API key is set, mock mode should:
- Acknowledge photo receipt
- Generate framework-compliant mock responses (question-first, specific, brief)
- Return `is_mock: true` so the console shows it's simulated

**Live mode with photos:** Claude Haiku 4.5 supports vision. Pass the image URL directly:
```python
messages=[{
    "role": "user",
    "content": [
        {"type": "image", "source": {"type": "url", "url": media_url}},
        {"type": "text", "text": f"Worker ({trade}, {experience}): {body}"}
    ]
}]
```

### Priority 3: System Prompt Adaptation (SafetyTAP → SMS)

SafetyTAP's prompt targets 30-60 words for a one-shot Telegram interaction. Safety as a Contact delivers via SMS (160-char segments, ongoing relationship). The adaptation:

| SafetyTAP | Safety as a Contact |
|-----------|-------------------|
| 30-60 words | 160-320 chars (1-2 SMS segments) |
| One-shot, no follow-up | Ongoing coaching relationship |
| Stateless | Worker context (trade, experience, history) |
| No opt-out needed | "Reply STOP to opt out" compliance |
| Photo always available | Photo optional (MMS), text also valid |

The core voice, decision tree, universal rules, and prohibited language carry over unchanged. The only adaptations are message length and SMS compliance requirements.

### Priority 4: Test Console Photo Support

The test console needs to simulate MMS:
- URL input field or file upload next to the message input
- Simulate endpoint accepts `image_url` parameter
- Photo thumbnail displayed in chat bubble
- Metadata panel shows "Photo analyzed" indicator

---

## What We Keep (Infrastructure Is Solid)

Everything below stays as-is:

- Database models and schema (add `media_urls` field to Observation)
- Consent management (double opt-in, opt-out, all TCPA compliance)
- SMS sender with compliance checks (window, rate limit, consent)
- Message logging and audit trail
- Test console architecture (simulate endpoint, conversations, stats)
- Trade calibration data (12 trades, fuzzy matching)
- Health check and structured logging
- All existing test infrastructure
- Server configuration and deployment setup

---

## Decision Point

Before building further, we need alignment on:

1. **Is the SafetyTAP Response Framework the source of truth for Safety as a Contact's coaching voice?** (My read: yes, with SMS-specific adaptations.)

2. **Is photo submission the primary use case, with text-only as secondary?** (My read: yes. Workers snap a photo of what they see. Text is supplementary context.)

3. **Should the system prompt be adapted from SafetyTAP's `system-prompt.txt`, or written fresh?** (My recommendation: adapt directly. The SafetyTAP prompt is battle-tested and represents significant prompt engineering investment.)

4. **For mock mode (no API key), how should we handle photo simulation?** (My recommendation: mock mode acknowledges the photo and returns framework-compliant template responses. The console shows a "MOCK — no vision analysis" indicator.)

5. **SMS length constraint: target 160 chars (1 segment) or allow 320 chars (2 segments)?** (SafetyTAP targets 30-60 words ≈ 150-300 chars. Two SMS segments feels right for coaching depth while staying brief.)

---

## File Inventory

### Backend (18 files, ~2,100 lines)

```
backend/
  __init__.py
  main.py              47 lines — FastAPI app, routes, console page
  config.py            43 lines — Environment config (Pydantic Settings)
  database.py          47 lines — SQLAlchemy engine, session, init
  models.py           145 lines — 7 ORM models + phone hashing
  logging_config.py    35 lines — Structured logging setup
  api/
    __init__.py
    health.py          19 lines — GET /health
    deps.py             2 lines — Shared dependencies
    console.py        231 lines — Test console API (simulate, stats, reset)
  sms/
    __init__.py
    handler.py        170 lines — Twilio webhook + handle_inbound_message()
    sender.py          88 lines — send_sms() with compliance
    consent.py        140 lines — Opt-in/out management
    compliance.py      66 lines — Sending window, rate limits
  coaching/
    __init__.py
    engine.py         292 lines — Mock + live coaching pipeline
    prompts.py        113 lines — System prompt templates (NEEDS REWRITE)
    trades.py         221 lines — 12 trade profiles + fuzzy matching
  templates/
    console.html      497 lines — Chat-style test console UI
```

### Tests (5 files, ~1,060 lines, 94 tests)

```
tests/
  __init__.py
  conftest.py         146 lines — Fixtures, test DB, seed data
  test_coaching_engine.py   167 lines — 24 tests
  test_console.py           167 lines — 11 tests
  test_trades.py             93 lines — 11 tests
  test_sms_handler.py       134 lines — 5 tests
  test_compliance.py         (Phase 2) — 10 tests
  test_consent.py            (Phase 2) — 8 tests
  test_models.py             (Phase 2) — 9 tests
  test_database.py           (Phase 2) — 2 tests
  test_integration.py        (Phase 2) — 4 tests
  test_config.py             (Phase 2) — 3 tests
  test_health.py             (Phase 2) — 1 test
  test_sms_sender.py         (Phase 2) — 6 tests
```

### Config

```
requirements.txt      28 lines — All Python dependencies
pyproject.toml        14 lines — pytest + ruff config
run.py                 6 lines — Dev server launcher (port 8002)
```

### Reference Documents

```
docs/
  PRODUCT_VISION.md          — Core product philosophy
  ARCHITECTURE.md            — Technical architecture + data flow
  BEHAVIORAL_FRAMEWORK.md    — 8 behavioral science frameworks
  BRAND_GUIDE.md             — Voice, colors, typography
  SMS_COMPLIANCE.md          — TCPA/CTIA developer reference
  DEVELOPMENT_PLAN.md        — 6-phase build plan

SafetyTAP (source of truth for coaching voice):
  RESPONSE_FRAMEWORK.md      — 5 modes, decision tree, universal rules, anti-patterns
  SYSTEM_PROMPT.md           — Executable system prompt + implementation notes
  system-prompt.txt          — Production system prompt (latest version)
```
