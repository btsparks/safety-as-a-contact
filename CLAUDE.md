# Safety as a Contact

SMS-delivered behavioral safety coaching for construction. Workers save a phone number, text hazard observations, and receive AI-powered coaching responses grounded in their company's own safety documents. Their observations feed back into toolbox talks — closing the feedback loop.

**This is NOT a chatbot. NOT a dashboard. It is a behaviorally engineered coaching system delivered through the most accessible channel in construction: a text message.**

## Core Philosophy

- Human behavior first, technology second
- Every interaction is a coaching moment, not data collection
- The feedback loop IS the product (observation -> coaching -> toolbox talk -> worker sees impact)
- Workers are assets to develop, not problems to control
- The AI is a resource assistant, NOT a safety expert — no safety judgments, no engineering advice
- Psychological safety enables reporting; reporting enables learning; learning prevents incidents

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 / SQLite (dev) / PostgreSQL (prod)
- **SMS**: Telnyx REST API via httpx (no SDK dependency)
- **AI**: Anthropic Claude API — Haiku for coaching (sub-second), Sonnet for arc evaluation
- **Frontend**: Astro + Tailwind CSS (marketing site at safetyasacontact.com)
- **Domain**: safetyasacontact.com (Vercel)

## Key Commands

- Run backend: `python run.py` → http://localhost:8002
- Run frontend: `cd site && npm run dev` → http://localhost:4322
- Run tests: `pytest tests/` (from project root, venv activated)
- Run tests with coverage: `pytest --cov=backend tests/`
- Run eval pipeline: `python -m training gate --sessions 10`
- Run live validation: `python -m tests.live_validation`
- Ingest Wollam docs: `python -m scripts.ingest_wollam_docs`
- Activate venv: `source venv/Scripts/activate` (Windows/Git Bash)

## Coaching Engine Architecture (CRITICAL)

The coaching engine is the core product. The AI is a **document-grounded resource assistant**, not a trade expert.

### Three Response Modes (Post-Pivot)

1. **ACKNOWLEDGE + REFERENCE** — When documents match the observation. Quote/paraphrase with attribution, ask reflective question.
2. **ACKNOWLEDGE + REFLECT** — When no docs match or observation is behavioral. Say honestly docs don't cover it, ask reflective question.
3. **ACKNOWLEDGE + CONNECT** — When worker's trade doesn't match observation. Connect to their trade context, ask how it relates.

### Hard Liability Rules (Non-Negotiable)

The AI NEVER:
- Evaluates safety or makes safety judgments
- Provides engineering advice or tells workers what to do
- Implies trade knowledge or technical authority
- Cites OSHA unless quoting from uploaded documents
- Uses first person ("I") or reveals it is AI
- Presents unsourced information

### Document-Grounded Model

Coaching responses are grounded in the company's own safety documents (site safety plans, company procedures, incident reports). The `backend/documents/retrieval.py` module does keyword-based search with Spanish-to-English expansion. Documents are ingested via `backend/documents/ingestion.py` and stored as searchable sections in the `safety_documents` table.

### Assessment (Invisible to Worker)

Every response includes metadata (separated by `|||`): response_mode, hazard_category, document_referenced, specificity_score, worker_engagement, worker_confidence, teachable_moment, suggested_next_direction. The worker only ever experiences a helpful conversation.

## Code Style

- Python: Follow PEP 8, use type hints on all functions, ruff for formatting
- TypeScript/JS: ES modules, Prettier formatting, no semicolons
- SQL: Lowercase keywords, snake_case for tables/columns
- All SMS message templates must be under 380 characters (2 SMS segments)
- Never hardcode phone numbers, API keys, or secrets — use environment variables
- Every SMS interaction must check consent status before sending

## Architecture Rules

- All AI coaching responses go through the behavioral engine — never send raw LLM output directly to workers
- SMS messages must comply with TCPA, CTIA, and A2P 10DLC requirements at all times
- Consent must be verified before EVERY outbound message — no exceptions
- Anonymous reporting must always be available — never force identification
- Opt-out processing must happen within the same message session (immediate)
- Spanish language support is a core requirement — detect language, respond in kind
- Photo/MMS is the PRIMARY use case — text-only is the fallback
- Every coaching interaction is a CONVERSATION (multi-turn), not a one-shot response
- The AI silently assesses worker progression — the worker NEVER experiences this as testing

## SMS Provider: Telnyx

- REST API via httpx (no Python SDK)
- Outbound: `POST https://api.telnyx.com/v2/messages` with Bearer token
- Inbound webhook: JSON body (not form data), `event_type: "message.received"`
- MMS media URLs are temporary — photos downloaded immediately on receipt
- Webhook signature validation: ed25519 (requires PyNaCl for production)
- Phone: +18013163196 (Midvale, UT 801 area code)
- A2P 10DLC: Brand registration pending (KYC verification in progress)

## Headless Evaluation Pipeline

7-agent system for testing coaching quality without manual review:

| Agent | Role | Model |
|-------|------|-------|
| Worker AI | Generate realistic worker messages | Haiku |
| Coaching AI | The product under test (unmodified) | Haiku |
| Response Evaluator | Mechanical scoring (word count, questions, prohibited) | Haiku |
| Hazard Evaluator | Independent hazard ground truth | Haiku |
| Behavioral Auditor | 8-framework behavioral science scoring | Haiku |
| Authenticity Judge | "Would a real foreman text this?" | Haiku |
| Arc Evaluator | Longitudinal trajectory across sessions | Sonnet |

### Quality Gate (6 Categories)
1. **Compliance** (hard pass/fail): word count, char count, no first-person, no prohibited, no safety judgments
2. **Response Quality** (graded): question ratio >75%, mode appropriateness, document grounding, no technical advice
3. **Behavioral Science** (graded): composite >3.5, psychological safety >4.0
4. **Authenticity** (graded): sounds human >3.5, trade credible >3.0
5. **Longitudinal Coherence** (graded): evolution >3.0, coherence >3.5
6. **Stress Test** (pass/fail): >90% chaos handling

### CLI Commands
```bash
python -m training evaluate miguel --sessions 10 --turns 4
python -m training gate --sessions 10              # All 3 core personas
python -m training report --latest
```

## Project Structure

```
backend/                  # FastAPI backend
  main.py                 # App entry point, router wiring, console/training routes
  config.py               # pydantic-settings from .env (Telnyx, Anthropic)
  database.py             # Engine, session, init_db()
  models.py               # SQLAlchemy models (14 tables)
  logging_config.py       # Structured JSON logging
  api/
    health.py             # GET /health
    console.py            # Dev console API
    training.py           # Training review + simulation API
    documents.py          # Document management API
    deps.py               # Shared dependencies
  coaching/
    engine.py             # Coaching response generation, session management
    prompts.py            # System prompt architecture (document-grounded model)
    profile.py            # Worker longitudinal profiles + mentor notes
    trades.py             # 12 trade profiles with coaching focus
  documents/
    retrieval.py          # Keyword search + Spanish expansion (56 ES→EN terms)
    ingestion.py          # Document chunking + storage (min 80 char sections)
    pdf_extractor.py      # PDF text extraction (PyMuPDF)
    insights.py           # Observation pattern analysis
  sms/
    handler.py            # POST /api/sms/inbound (Telnyx JSON webhook)
    sender.py             # send_sms() via Telnyx REST API
    consent.py            # Opt-in/opt-out/verification
    compliance.py         # Sending window, rate limits
  templates/
    console.html          # SMS test console UI
    training.html         # Training review UI
    simulations.html      # Simulation review UI
training/                 # Headless evaluation pipeline
  __main__.py             # CLI: evaluate, simulate, gate, report
  quality_gate.py         # Quality gate thresholds (6 categories)
  simulator.py            # Multi-session simulation engine
  personas.py             # 5 test personas (Miguel, Jake, Ray, Carlos, Diana)
  worker_ai.py            # AI worker message generator with chaos modes
  report.py               # Terminal + JSON report formatting
  models.py               # Training DB models
  evaluators/             # 5 independent evaluator agents
    response_eval.py      # Mechanical/structural scoring
    hazard_eval.py        # Hazard recognition accuracy
    behavioral_eval.py    # 8 behavioral science frameworks
    authenticity_eval.py  # Human voice + trade credibility
    arc_eval.py           # Longitudinal coherence (Sonnet)
tests/                    # pytest test suite (205+ tests)
scripts/
  ingest_wollam_docs.py   # PDF ingestion for Wollam safety documents
docs/                     # Product + technical documentation
site/                     # Astro marketing site (deployed to Vercel)
run.py                    # Dev server launcher (port 8002)
requirements.txt          # Python dependencies
pyproject.toml            # Project config + pytest settings
```

## Brand Voice (for any user-facing text)

- Tone: Direct, warm, knowledgeable — like a trusted foreman, not a corporate memo
- Use "crew, team, hands" not "workforce, personnel"
- Use "good catch" not "positive safety behavior identified"
- Use "text us" not "submit a report"
- Colors: Safety Amber #E8922A, Deep Slate #1E2A3B, Concrete #F2F0EC
- Fonts: DM Sans (headlines), Inter (body)

## SMS Compliance (CRITICAL)

- A2P 10DLC campaign must be registered and approved before ANY production messaging
- Double opt-in consent flow is MANDATORY
- Every outbound message must include opt-out language (Reply STOP to unsubscribe)
- Sending window: 8am-9pm recipient's local time ONLY
- Consent records must be stored with timestamp, method, and IP for 5 years
- See `docs/TELNYX_10DLC_REGISTRATION.md` for registration details

## Workflow

- Always check SMS compliance before implementing any messaging feature
- Run tests after any change to coaching engine or SMS handling
- Use Plan Mode before implementing features that touch 3+ files
- Commit frequently with descriptive messages
- Never push to main without tests passing

## Additional Context

- `docs/PRODUCT_VISION.md` — Full product philosophy and paradigm shift explanation
- `docs/ARCHITECTURE.md` — Technical architecture and data flow
- `docs/BEHAVIORAL_FRAMEWORK.md` — 7 behavioral science frameworks
- `docs/BRAND_GUIDE.md` — Brand voice, colors, typography
- `docs/PIVOT_PLAN.docx` — Architectural pivot from trade-expert to document-grounded model
- `docs/TELNYX_10DLC_REGISTRATION.md` — Telnyx A2P registration details
- `docs/SMS_COMPLIANCE.md` — TCPA/CTIA requirements, consent management
