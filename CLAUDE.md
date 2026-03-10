# Safety as a Contact

SMS-delivered behavioral safety coaching for construction. Workers save a phone number, text hazard observations, and receive AI-powered coaching responses grounded in behavioral science. Their observations feed back into toolbox talks — closing the feedback loop.

**This is NOT a chatbot. NOT a dashboard. It is a behaviorally engineered coaching system delivered through the most accessible channel in construction: a text message.**

## Core Philosophy

- Human behavior first, technology second
- Every interaction is a coaching moment, not data collection
- The feedback loop IS the product (observation -> coaching -> toolbox talk -> worker sees impact)
- Workers are assets to develop, not problems to control
- The foreman is the key adoption persona — empower them with coaching prompts, not scripts
- Psychological safety enables reporting; reporting enables learning; learning prevents incidents

## Tech Stack

- **Backend**: Python (Flask or FastAPI) + SQLAlchemy + PostgreSQL
- **SMS**: Twilio Programmable Messaging (A2P 10DLC registered)
- **AI**: Anthropic Claude API for coaching engine
- **Frontend**: Astro + Tailwind CSS (marketing site + admin portal)
- **Hosting**: Railway or Render (simple, affordable for MVP)
- **Domain**: safetyasacontact.com

## Key Commands

- Run dev server: `npm run dev` (frontend) / `python -m flask run` (backend)
- Run tests: `pytest` (backend) / `npm test` (frontend)
- Type check: `mypy src/` (backend)
- Lint: `ruff check src/` (backend) / `npm run lint` (frontend)
- DB migrations: `flask db upgrade`

## Code Style

- Python: Follow PEP 8, use type hints on all functions, ruff for formatting
- TypeScript/JS: ES modules, Prettier formatting, no semicolons
- SQL: Lowercase keywords, snake_case for tables/columns
- All SMS message templates must be under 160 characters per segment
- Never hardcode phone numbers, API keys, or secrets — use environment variables
- Every Twilio interaction must check consent status before sending

## Architecture Rules

- All AI coaching responses go through the behavioral engine — never send raw LLM output directly to workers
- SMS messages must comply with TCPA, CTIA, and A2P 10DLC requirements at all times
- Consent must be verified before EVERY outbound message — no exceptions
- The coaching engine uses 5 response modes: Alert, Validate, Nudge, Probe, Affirm
- Responses must be trade-aware (12 trades) and experience-level calibrated
- Anonymous reporting must always be available — never force identification
- All worker data is encrypted at rest and in transit
- Opt-out processing must happen within the same message session (immediate)
- Spanish language support is a core requirement (not optional) — detect language, respond in kind
- Consent flows, opt-out messages, and compliance text must work in both English and Spanish

## Brand Voice (for any user-facing text)

- Tone: Direct, warm, knowledgeable — like a trusted foreman, not a corporate memo
- Use "crew, team, hands" not "workforce, personnel"
- Use "good catch" not "positive safety behavior identified"
- Use "text us" not "submit a report"
- Second person ("you") is default — we talk TO people, not ABOUT safety
- Colors: Safety Amber #E8922A, Deep Slate #1E2A3B, Concrete #F2F0EC
- Fonts: DM Sans (headlines), Inter (body)

## SMS Compliance (CRITICAL)

- A2P 10DLC campaign must be registered and approved before ANY production messaging
- Double opt-in consent flow is MANDATORY: worker texts in -> confirmation -> reply YES -> enrolled
- Every outbound message must include opt-out language (Reply STOP to unsubscribe)
- Sending window: 8am-9pm recipient's local time ONLY
- Consent records must be stored with timestamp, method, and IP for 5 years
- See @.claude/skills/twilio-a2p/SKILL.md for full compliance requirements

## Project Structure

```
src/
  api/              # Flask/FastAPI routes
  models/           # SQLAlchemy models (workers, observations, consent, companies)
  coaching/         # Behavioral coaching engine (THE core product logic)
    engine.py       # Main coaching orchestrator
    modes.py        # Alert, Validate, Nudge, Probe, Affirm response modes
    trades.py       # Trade-specific calibration (12 trades)
    prompts.py      # Claude API prompt templates
  sms/              # Twilio integration layer
    handler.py      # Inbound/outbound message processing
    consent.py      # Consent management (opt-in/opt-out)
    compliance.py   # TCPA/CTIA/A2P compliance checks
  feedback/         # Feedback loop engine
    toolbox.py      # Observation -> toolbox talk generation
    nudges.py       # Proactive shift-start coaching nudges
  portal/           # Admin portal backend
docs/               # Product documentation
  PRODUCT_VISION.md
  ARCHITECTURE.md
  DEVELOPMENT_PLAN.md
  BEHAVIORAL_FRAMEWORK.md
  BRAND_GUIDE.md
  SMS_COMPLIANCE.md
site/               # Astro marketing site + consent pages
  src/pages/
    index.astro     # Landing page
    privacy.astro   # Privacy policy (required for A2P)
    terms.astro     # Terms of service (required for A2P)
    sms-terms.astro # SMS-specific terms (required for A2P)
    consent.astro   # Web consent page
tests/
  test_coaching/    # Coaching engine tests
  test_sms/         # SMS handling tests
  test_compliance/  # Compliance verification tests
```

## Workflow

- Always check SMS compliance before implementing any messaging feature
- Run tests after any change to coaching engine or SMS handling
- Use Plan Mode before implementing features that touch 3+ files
- When adding new coaching response types, update both the engine AND the test suite
- Commit frequently with descriptive messages
- Never push to main without tests passing

## Context Management

- When compacting, always preserve: current feature scope, active file list, compliance requirements, and the 5 coaching response modes
- Between major features, use /clear to reset context
- Reference docs/ files for detailed context rather than repeating information in conversation

## Additional Context

- @docs/PRODUCT_VISION.md — Full product philosophy and paradigm shift explanation
- @docs/ARCHITECTURE.md — Detailed technical architecture and data flow
- @docs/BEHAVIORAL_FRAMEWORK.md — The 7 behavioral science frameworks and how they map to features
- @docs/BRAND_GUIDE.md — Complete brand voice, colors, typography, and messaging rules
- @docs/SMS_COMPLIANCE.md — Twilio A2P registration, TCPA/CTIA requirements, consent management
- @docs/DEVELOPMENT_PLAN.md — Phased build plan with priorities
