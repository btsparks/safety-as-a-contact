# Safety as a Contact - Technical Architecture

SMS-based behavioral safety coaching platform for construction workers.

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 / SQLite (dev) / PostgreSQL (prod)
- **SMS**: Telnyx REST API via httpx (no SDK dependency)
- **AI**: Anthropic Claude API — Haiku for coaching, Sonnet for arc evaluation
- **Frontend**: Astro + Tailwind CSS (marketing site)
- **Hosting**: Render (backend) + Vercel (marketing site)
- **Domain**: safetyasacontact.com

## System Architecture

### Inbound Flow (Worker Observation)
1. Worker texts Telnyx 10DLC number with hazard observation (text and/or photo)
2. Telnyx webhook hits `POST /api/sms/inbound` with JSON payload
3. Webhook signature validation (ed25519) + rate limiting
4. Consent check: verify phone_number has active consent record
5. If MMS: download media immediately (Telnyx URLs are temporary)
6. Coaching engine retrieves relevant safety documents for context
7. Call Claude Haiku with document-grounded system prompt + worker context
8. Parse response: coaching text + assessment metadata (split on `|||`)
9. Truncate at sentence boundary if > 380 chars
10. Send response via Telnyx REST API, log to message_log

### Document-Grounded Coaching Model
1. Worker observation keywords extracted (with Spanish → English expansion)
2. `retrieve_relevant_documents()` searches safety_documents table by keyword match
3. Matched documents injected into system prompt as context
4. AI selects one of 3 response modes:
   - **ACKNOWLEDGE + REFERENCE**: Documents match → quote with attribution + reflective question
   - **ACKNOWLEDGE + REFLECT**: No match → honest about gap + reflective question
   - **ACKNOWLEDGE + CONNECT**: Trade mismatch → connect to worker's context + question
5. Assessment metadata returned invisibly (response_mode, hazard_category, specificity, etc.)

### Multi-Turn Conversation Flow
- Sessions resume within 4 hours of last message
- After 4 hours of silence, new session starts
- Thread history (last 6 turns) included in prompt for context
- Worker tier (1-4) adapts coaching depth invisibly

## Database Schema (Current — 14+ tables)

```
companies
  id (PK), name, standards_config (JSON), created_at

projects
  id (PK), company_id (FK), name, location, description, active, created_at

workers
  id (PK), phone_number (hashed SHA256), company_id (FK), project_id (FK),
  trade, experience_level (entry/intermediate/expert),
  preferred_language (en/es), first_name, active_project_id, created_at

consent_records
  id (PK), phone_number (hashed), consent_type, consent_method,
  consented_at, revoked_at, is_active, ip_address, created_at

observations
  id (PK), worker_id (FK nullable), project_id (FK), session_id (FK),
  raw_text, hazard_category, severity, trade_context, language,
  media_urls (JSON), ai_analysis (JSON), created_at

coaching_responses
  id (PK), observation_id (FK), response_mode (reference/reflect/connect),
  response_text, message_sid, sent_at, status

coaching_sessions
  id (PK), worker_id (FK), phone_hash, started_at, ended_at,
  turn_count, focus_area, coaching_direction, session_sentiment,
  worker_tier_at_time, response_modes_used (JSON), media_urls (JSON),
  hazard_identified, hazard_category, teachable_moment, session_closed

worker_profiles
  id (PK), phone_hash (unique), tier, progression_markers (JSON),
  mentor_notes (JSON), document_exposure (JSON), baseline_complete,
  total_interactions, last_interaction_at

interaction_assessments
  id (PK), session_id (FK), turn_number, response_mode,
  specificity_score, worker_engagement, worker_confidence,
  photo_present, question_asked, teachable_moment

safety_documents
  id (PK), project_id (FK nullable), title, content, category,
  section_label, trade_tags (JSON), hazard_tags (JSON),
  source_attribution, language, created_at

document_references
  id (PK), phone_hash, session_id (FK), document_id (FK),
  observation_id (FK), created_at

message_log
  id (PK), phone_number (hashed), direction (inbound/outbound),
  message_type, message_sid, content_preview, sent_at, delivery_status
```

## API Routes

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sms/inbound` | POST | Telnyx webhook for incoming SMS/MMS |
| `/api/health` | GET | Health check (database, API connectivity) |
| `/api/documents/upload` | POST | Upload and chunk a safety document |
| `/api/documents/search` | POST | Search documents by keyword |
| `/api/documents/list` | GET | List all ingested documents |
| `/api/test/simulate` | POST | Console: simulate worker message |
| `/api/test/conversations` | GET | Console: list recent conversations |
| `/api/test/stats` | GET | Console: coaching stats |
| `/api/training/photos` | GET | Training: list analyzed photos |
| `/api/training/converse` | POST | Training: send message through coaching engine |
| `/console` | GET | Dev-only SMS test console (HTML) |
| `/training` | GET | Dev-only training review interface (HTML) |

Telnyx inbound uses ed25519 signature verification. Console/training endpoints are dev-only (disabled in production unless DEMO_MODE=true).

## Coaching Engine Architecture

Core product logic in `backend/coaching/`:

1. **Parse**: Extract phone, message text, media URLs from Telnyx JSON webhook
2. **Context**: Fetch or create worker profile, get trade/tier/language
3. **Session**: Resume existing session (< 4 hours) or start new one
4. **Retrieve**: Search safety_documents for relevant content via keyword matching
5. **Build Prompt**: Assemble document-grounded system prompt with:
   - Identity block (resource assistant, not expert)
   - Worker context (trade, tier, language, project)
   - Document context (matched sections with attribution)
   - Brevity rules (25-40 words, 380 chars max)
   - Response mode guidance (reference/reflect/connect)
   - Question mandate (3:1 ratio)
   - Assessment output format (JSON after `|||`)
6. **Call Claude**: Haiku, temperature 0.3, max_tokens 500
7. **Parse Response**: Split coaching text from assessment JSON on `|||`
8. **Truncate**: Sentence-boundary truncation if > 380 chars
9. **Persist**: Save coaching response, assessment, update session + profile

## Security & Privacy

- **Phone Hashing**: SHA256(phone_number + configurable SALT) for anonymous reporting
- **Consent Immutability**: Soft delete only (set revoked_at), never hard delete
- **Retention**: 5-year consent record retention (TCPA compliance)
- **No PII Logs**: All logs sanitized, phone_numbers masked
- **Rate Limiting**: 5 messages/phone/day, 8am-9pm sending window
- **Telnyx Validation**: ed25519 signature verification on inbound webhooks (requires PyNaCl)
- **Secrets**: All sensitive values via environment variables, never in code

## Environment Variables

```
ENVIRONMENT=development|production
SECRET_KEY=<random-string>
PHONE_HASH_SALT=<random-string>
DATABASE_URL=sqlite:///safety_as_a_contact.db  # or postgresql://...
ANTHROPIC_API_KEY=sk-ant-...
TELNYX_API_KEY=KEY...
TELNYX_PHONE_NUMBER=+18013163196
TELNYX_MESSAGING_PROFILE_ID=<uuid>
TELNYX_PUBLIC_KEY=<base64-ed25519-public-key>
DEMO_MODE=false
LOG_LEVEL=INFO
MAX_MESSAGES_PER_PHONE_PER_DAY=5
SENDING_WINDOW_START=8
SENDING_WINDOW_END=21
SESSION_PAUSE_MINUTES=30
SESSION_TIMEOUT_MINUTES=240
```

## Data Flow Diagrams (Text)

**Worker Observation Flow**:
Worker → SMS → Telnyx → Webhook Handler → Consent Validation → Document Retrieval → Coaching Engine → Claude Haiku → Response Parsing + Truncation → Telnyx Send → Worker SMS

**Document Ingestion Flow**:
PDF → PyMuPDF Extraction → Header/Footer Stripping → Section Splitting → Hazard Tag Auto-Detection → safety_documents Table → Available for Retrieval

**Evaluation Pipeline Flow**:
Worker AI (Haiku) → Coaching AI (Haiku, under test) → 4 Per-Response Evaluators (Haiku) → Arc Evaluator (Sonnet) → Quality Gate (6 categories) → Report

## Headless Evaluation Pipeline

Located in `training/`. Runs coaching engine against simulated workers to measure quality:

- **5 Personas**: Miguel (ES/laborer), Jake (EN/ironworker), Ray (EN/operator), Carlos (ES/bilingual), Diana (EN/apprentice)
- **7 Independent Agents**: Worker AI, Coaching AI (product under test), Response Eval, Hazard Eval, Behavioral Eval, Authenticity Eval, Arc Eval
- **Quality Gate**: 6 categories with pass/fail/warn thresholds
- **CLI**: `python -m training gate --sessions 10 --prompt-version "v1.0"`
- **Reports**: JSON + terminal output, saved to `training_reports/`
