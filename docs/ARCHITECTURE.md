# Safety as a Contact - Technical Architecture

SMS-based behavioral safety coaching platform for construction workers.

## Tech Stack

- **Backend**: Python (FastAPI) + SQLAlchemy + PostgreSQL
- **SMS**: Twilio Programmable Messaging (A2P 10DLC registered)
- **AI**: Anthropic Claude API for coaching response generation
- **Frontend**: Astro + Tailwind CSS (marketing site + admin portal)
- **Hosting**: Railway or Render
- **Domain**: safetyasacontact.com

## System Architecture

### Inbound Flow (Worker Observation)
1. Worker texts Twilio short code with hazard observation
2. Twilio webhook hits `POST /api/sms/inbound`
3. Webhook signature validation + rate limiting
4. Consent check: verify phone_number is in active consent_records
5. Coaching engine classifies message (hazard observation vs question vs opt-in/out)
6. If observation: extract trade context, hazard category, severity
7. Call Claude API with behavioral coaching system prompt
8. Validate response (length, tone, compliance)
9. Send via Twilio Messaging Service (async, tracked via message_log)

### Outbound Flow (Proactive Nudges)
1. Scheduler triggers every 24/48 hours (configurable per company)
2. Look up workers with active consent + recent observation patterns
3. Compliance checks: correct time window (business hours), daily frequency cap
4. Nudge generator creates contextual prompt (e.g., "Safety topic reminder")
5. Call Claude API with worker's trade, recent hazards, engagement level
6. Send via Twilio, log in message_log with status tracking

### Feedback Loop (Toolbox Talks)
1. Observations aggregated per project (daily/weekly)
2. Toolbox talk generator queries top hazard categories by severity
3. Call Claude API to synthesize observations into toolbox talk content
4. Create toolbox_talks record with source observation IDs
5. Send prompt to foreman via SMS or portal notification
6. Foreman acknowledges delivery, conducts talk with crew
7. Workers confirm attendance via SMS callback
8. engagement_metrics updated with loop_closures count

## Database Schema

```
companies
  id (PK), name, standards_config (JSON), created_at

projects
  id (PK), company_id (FK), name, location, active, created_at

workers
  id (PK), phone_number (hashed SHA256), company_id (FK), project_id (FK),
  trade, experience_level (entry/intermediate/expert),
  preferred_language (en/es, default en), created_at

consent_records
  id (PK), phone_number (hashed), consent_type (sms_coaching),
  consent_method (double_opt_in), consented_at, revoked_at, is_active,
  ip_address, created_at

observations
  id (PK), worker_id (FK nullable), project_id (FK), raw_text,
  hazard_category (enum), severity (1-5), trade_context, language (en/es),
  ai_analysis (JSON), created_at

coaching_responses
  id (PK), observation_id (FK), response_mode (alert/validate/nudge/probe/affirm),
  response_text, twilio_sid, sent_at, status

toolbox_talks
  id (PK), project_id (FK), title, content, source_observations (int[]),
  generated_at, delivered_at, delivery_status

foreman_prompts
  id (PK), foreman_worker_id (FK), toolbox_talk_id (FK), prompt_text,
  context_notes, created_at, acknowledged_at

engagement_metrics
  id (PK), worker_id (FK), observation_count, response_rate (0-1),
  loop_closures, engagement_score (0-100), period_start, period_end

message_log
  id (PK), phone_number (hashed), direction (inbound/outbound),
  message_type (observation/nudge/toolbox_talk/acknowledgment),
  twilio_sid, content_preview, sent_at, delivery_status
```

## API Routes

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sms/inbound` | POST | Twilio webhook for incoming SMS |
| `/api/sms/status` | POST | Twilio delivery status callback |
| `/api/portal/dashboard` | GET | Admin dashboard main view |
| `/api/portal/observations` | GET | Observation feed with filtering/sorting |
| `/api/portal/toolbox-talk` | POST | Generate toolbox talk from observations |
| `/api/portal/engagement` | GET | Engagement metrics and Safety Engagement Score |
| `/api/portal/company` | POST | Create/update company standards config |
| `/api/portal/project` | POST/GET | Project CRUD operations |
| `/api/portal/consent` | GET | View consent records for compliance audit |
| `/api/health` | GET | Health check (database, Twilio, Claude API) |

All endpoints require Bearer token authentication (JWT). Twilio inbound/status endpoints use signature verification instead.

## Coaching Engine Architecture

Core product logic. Sits between inbound SMS and Twilio response:

1. **Parse**: Extract text, sender phone_number, timestamp from Twilio webhook
2. **Classify**: Is this observation/question/opt-in/opt-out? Use Claude classifier
3. **Context**: Fetch worker trade, experience level, company standards from DB
4. **Detect**: Hazard category, severity, relevance to worker's trade
5. **Select Mode**: Choose response type based on observation context
   - Alert: Critical hazard (severity 5) — urgent, direct language
   - Validate: Confirms observation, reinforces correct behavior
   - Nudge: Questions worker's decision, gentle redirection
   - Probe: Asks for more info, deepens reflection
   - Affirm: Positive reinforcement for safe behavior
6. **Build Prompt**: System prompt + worker context + recent observation patterns
7. **Call Claude**: `messages.create()` with coaching system prompt, max_tokens=200
8. **Validate Response**: Length (≤160 chars per SMS segment), tone check, no PII
9. **Send**: Async task to Twilio Messaging Service, track in message_log

### Coaching System Prompt Template
```
You are a behavioral safety coach for construction workers. Respond in 160 characters max, conversational tone.
Worker: {trade}, {experience_level}
Company Standards: {standards_config}
Recent observations: {last_5_observations}
Respond in {response_mode} mode to: {observation_text}
```

## Security & Privacy

- **Phone Hashing**: SHA256(phone_number + SALT) for anonymous reporting
- **Encryption**: PostgreSQL TDE at rest, TLS 1.3 in transit
- **Consent Immutability**: Soft delete only (set revoked_at), never hard delete
- **Retention**: 5-year consent record retention (TCPA compliance)
- **No PII Logs**: All logs sanitized, phone_numbers masked
- **Rate Limiting**: 10 req/min per IP on public endpoints, 100 req/min per worker
- **Twilio Validation**: Signature verification on all inbound webhooks
- **DB Access**: Row-level security on observations (workers see only their own)

## Environment Variables

```
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
TWILIO_MESSAGING_SERVICE_SID=MG...
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://user:pass@host/dbname
SECRET_KEY=...
JWT_SECRET=...
ENVIRONMENT=development|staging|production
LOG_LEVEL=INFO
```

## Data Flow Diagrams (Text)

**Worker Observation Flow**:
Worker → SMS → Twilio → Webhook Handler → Consent Validation → Coaching Engine → Claude API (coaching prompt) → Response Validation → Twilio Send → Worker SMS

**Feedback Loop (Toolbox Talks)**:
Daily Aggregation → Top Hazards Per Project → Claude API (synthesis prompt) → Toolbox Talk Record → Foreman SMS/Portal → Foreman Delivery → Worker Confirmation SMS → engagement_metrics.loop_closures++

**Proactive Nudge Flow**:
Scheduler (24h interval) → Worker Context Lookup (trade, recent obs) → Compliance Check (consent active, time window, frequency cap) → Nudge Generator → Claude API (nudge prompt) → Twilio Send → Async Status Tracking

## Development Priorities

1. Inbound SMS handler + Coaching engine (core loop)
2. Consent management + TCPA compliance
3. Claude integration with response validation
4. Admin portal observations feed
5. Toolbox talk generation + foreman workflow
6. Engagement metrics calculation
7. Proactive nudge scheduler
