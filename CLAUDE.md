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

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 / SQLite (dev) / PostgreSQL (prod)
- **SMS**: Twilio Programmable Messaging (A2P 10DLC registered)
- **AI**: Anthropic Claude API for coaching engine
- **Frontend**: Astro + Tailwind CSS (marketing site + admin portal)
- **Hosting**: Railway or Render (simple, affordable for MVP)
- **Domain**: safetyasacontact.com

## Key Commands

- Run backend: `python run.py` → http://localhost:8000
- Run frontend: `cd site && npm run dev` → http://localhost:4322
- Run tests: `pytest tests/` (from project root, venv activated)
- Run tests with coverage: `pytest --cov=backend tests/`
- Health check: `curl localhost:8000/health`
- Activate venv: `source venv/Scripts/activate` (Windows/Git Bash)

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
- Photo/MMS is the PRIMARY use case — text-only is the fallback, not the default
- Every coaching interaction is a CONVERSATION (multi-turn), not a one-shot response
- Each conversation thread is cataloged as a complete coaching session
- The AI silently assesses worker progression — the worker NEVER experiences this as testing

## Coaching Engine (CRITICAL — Read the Skill)

The coaching engine is the core product. Before modifying ANY coaching logic,
system prompts, response templates, or conversation flow, you MUST read:
@.claude/skills/prompt-architecture/SKILL.md

This is the source of truth for how the AI thinks, converses, and assesses.
If it conflicts with any other document, the prompt architecture wins.

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
backend/                  # FastAPI backend (Phase 2+)
  main.py                 # App entry point, router wiring
  config.py               # pydantic-settings from .env
  database.py             # Engine, session, init_db()
  models.py               # 6 SQLAlchemy models (companies, projects, workers, consent_records, observations, message_log)
  logging_config.py       # Structured JSON logging
  api/
    health.py             # GET /health
    deps.py               # Shared dependencies
  sms/
    handler.py            # POST /api/sms/inbound (Twilio webhook)
    sender.py             # send_sms() with compliance checks
    consent.py            # Opt-in/opt-out/verification
    compliance.py         # Sending window, rate limits
tests/                    # pytest test suite (48 tests, 88% coverage)
docs/                     # Product documentation
site/                     # Astro marketing site (Phase 1, deployed)
run.py                    # Convenience launcher → localhost:8000
requirements.txt          # Python dependencies
pyproject.toml            # Project config + pytest settings
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
