# Safety as a Contact - Development Plan

**Owner:** Claude Code (automated development system)
**Project Lead:** Travis Sparks
**Duration:** 12 weeks
**Last Updated:** 2026-03-10

---

## Overview

This is a phased development plan that Claude Code will execute end-to-end. Travis Sparks is a non-developer project owner — Claude Code handles all implementation, testing, deployment, and verification.

Each phase includes clear deliverables and verification criteria. Build rules ensure compliance, quality, and architectural consistency.

---

## Phase 1: Foundation & Compliance (Weeks 1-2)

**Priority:** Obtain Twilio A2P campaign approval
**Owner:** Claude Code

### Deliverables

#### Marketing & Compliance Website (Astro + Tailwind)
- **Landing Page** (`safetyasacontact.com`)
  - Hero section: "Safety in Real-Time"
  - Value proposition: 5 core safety features
  - CTA: "Request Early Access"
  - Responsive design, mobile-first

- **Privacy Policy Page**
  - SMS-specific data collection section
  - CTIA non-sharing clause (critical for Twilio approval)
  - Data retention: 5 years for SMS consent records
  - Worker data protection statements
  - Opt-out instructions with STOP keyword info

- **Terms of Service Page**
  - User obligations and restrictions
  - SMS terms reference link
  - Limitation of liability
  - Dispute resolution

- **SMS Terms & Conditions Page**
  - Opt-in confirmation flow
  - Opt-out keywords and procedures
  - Message frequency disclosure
  - Charges notice (carrier rates apply)
  - Compliance footer on all pages

- **Web Consent Capture Page** (backup consent method)
  - Email + phone number form
  - Clear consent checkbox
  - Links to all compliance docs

**Brand Specifications:**
- Colors: Safety Amber (#E8922A), Deep Slate (#1E2A3B), Concrete (#F2F0EC)
- Fonts: DM Sans (headings), Inter (body) — via Google Fonts
- Deployment: Railway or Render (production URL)

#### Twilio Account Setup
- Create Twilio account
- Purchase 10DLC (long-code) phone number
- Create Messaging Service tied to 10DLC
- Document Service SID for backend configuration

#### A2P Campaign Registration
- **Step 1:** Submit brand registration (Twilio API)
  - Business name: Safety as a Contact
  - Use cases: Workplace safety coaching, observation confirmation
  - Website: safetyasacontact.com

- **Step 2:** Submit campaign registration (Twilio API)
  - Reference brand registration ID
  - Campaign name: "Safety Coaching Platform"
  - Message samples: coaching response, toolbox talk invite, confirmation

### Verification Checklist
- [ ] All website pages live at production URL
- [ ] Privacy Policy includes SMS-specific section and CTIA clause
- [ ] SMS Terms clearly list opt-out keywords
- [ ] Web consent page functional and tested
- [ ] Twilio 10DLC number active and ready
- [ ] Messaging Service created and documented
- [ ] Brand registration submitted in Twilio
- [ ] Campaign registration submitted in Twilio
- [ ] Can send test SMS without errors

---

## Phase 2: Core Backend (Weeks 2-4)

**Priority:** Build the system backbone
**Owner:** Claude Code

### Deliverables

#### FastAPI Project Foundation
- Python 3.11+ with FastAPI and Uvicorn
- Environment configuration (.env for secrets)
- Structured logging (JSON format for prod)
- Health check endpoints (`GET /health`)

#### Database & ORM (SQLAlchemy + PostgreSQL)
**Core Tables:**
- `companies` — customer organizations
- `projects` — safety programs within companies
- `workers` — individual workers (drivers, foremen, etc.)
- `consent_records` — SMS opt-in/opt-out audit trail
- `observations` — hazard observations from workers
- `coaching_responses` — AI-generated coaching messages
- `toolbox_talks` — daily safety briefings (aggregated from observations)
- `message_log` — complete SMS transaction history

**Indexes:** consent_phone_number, observation_timestamp, worker_company_id

#### Consent Management System
- Opt-in workflow: phone + company + acceptance → consent_records entry
- Opt-out workflow: STOP keyword → is_active=False, timestamp recorded
- Consent verification function: `verify_consent(phone, message_type)` → bool
- Consent retention: 5-year audit trail in database

#### Twilio Webhook Handler
- Receive inbound SMS via webhook
- Parse: from_number, message_body, timestamp
- Validate: consent exists and is_active
- Route to coaching engine or opt-out handler
- Respond within 1 second

#### Message Sending Service
- `send_sms(phone, message, compliance_checks=True)`
- Pre-send checks: consent verified, sending window valid, rate limit OK
- Post-send: log to message_log table
- Retry logic (exponential backoff, max 3 attempts)
- Twilio API integration with error handling

#### Monitoring & Observability
- Basic health endpoint: database connectivity, Twilio API status
- Simple metrics: SMS sent/received count per hour
- Error logging: all failures to structured log

### Verification Checklist
- [ ] FastAPI server runs locally (`uvicorn main:app --reload`)
- [ ] PostgreSQL database created with all tables
- [ ] Can receive inbound SMS via Twilio webhook
- [ ] Consent verification works end-to-end
- [ ] Can send outbound SMS via send_sms function
- [ ] Opt-out flow tested (STOP keyword triggers opt-out)
- [ ] Message log records all transactions
- [ ] Health check endpoint returns OK

---

## Phase 3: Coaching Engine (Weeks 4-6)

**Priority:** Build the core product — intelligent safety coaching
**Owner:** Claude Code

### Deliverables

#### Coaching Engine Orchestrator
- Receives observation (text, worker context, trade, experience level)
- Classifies observation (hazard type, severity)
- Selects response mode (Alert, Validate, Nudge, Probe, Affirm)
- Invokes Claude API with behavioral coaching system prompt
- Validates response (length, tone, compliance)
- Returns coaching response

#### 5 Response Modes
1. **Alert** — Immediate safety risk, urgent action needed
2. **Validate** — Affirm good safety thinking, reinforce behavior
3. **Nudge** — Gentle prompt to think deeper about the hazard
4. **Probe** — Ask clarifying questions about the situation
5. **Affirm** — Recognition and encouragement

#### Trade Calibration System (12 Trades)
- Concrete/Heavy Highway Construction
- Electrical
- HVAC
- Plumbing
- Roofing
- Heavy Equipment Operation
- Landscaping/Groundskeeping
- Painting/Coating
- Welding
- Demolition
- Steel Fabrication
- General Labor

Each trade has: common hazards, safety norms, typical equipment, regulatory focus

#### Experience Level Calibration
- Apprentice (0-2 years)
- Journeyman (2-8 years)
- Master (8+ years)

Coaching tone and complexity adjusted per level.

#### Claude API Integration
- System prompt: behavioral safety coaching framework
- Input: observation text, trade, experience level, hazard context
- Output: coaching response (targeted, actionable, tone-appropriate)
- Temperature: 0.7 (balanced creativity + consistency)
- Max tokens: 300

#### Response Validation
- Length: 50-300 characters (fits SMS + context)
- Tone check: professional, not condescending
- Compliance: no data collection requests, no legal advice
- Hazard accuracy: response addresses actual hazard

#### Observation Classification
- Hazard categories: environmental, equipment, procedural, ergonomic, behavioral
- Severity scale: low, medium, high, critical
- Trade context: matched against trade hazard database

### Verification Checklist
- [ ] Coaching engine responds to 10 test observations
- [ ] All 5 response modes work
- [ ] Responses generated within 5 seconds
- [ ] Trade calibration affects response tone (test 3+ trades)
- [ ] Experience level affects response depth
- [ ] Response validation catches out-of-spec responses
- [ ] Hazard classification matches safety standards
- [ ] No hallucinations or irrelevant advice in responses

---

## Phase 4: Feedback Loop (Weeks 6-8)

**Priority:** Close the loop — observations → toolbox talks → engagement
**Owner:** Claude Code

### Deliverables

#### Toolbox Talk Generation
- Aggregate observations from past 24 hours (per company)
- Group by hazard category and trade
- Generate 3-5 talking points for foreman
- Claude API call: summarize observations into safety talking points
- Output: structured toolbox talk (trade, talking points, hazard summary)

#### Foreman Coaching System
- Receive foreman request for "talking points on today's observations"
- Retrieve worker observations from last 24 hours
- Generate foreman briefing (how to discuss hazards with team)
- Include: context from observations, recommended discussion approach

#### Worker Confirmation Messages
- Send to worker: "Your observation about [hazard] was used in today's toolbox talk!"
- Reinforce behavior, close feedback loop
- Tracked in message_log

#### Proactive Shift-Start Nudges
- Morning message (8:00am local timezone): "Starting your shift? Text a safety observation when you spot a hazard."
- Gentle encouragement to engage with platform
- Scheduled via background job (APScheduler or Celery)

#### Safety Engagement Score
- Input: observations submitted, confirmations received, response rate
- Calculation: 40% observation frequency + 30% response rate + 30% confirmation engagement
- Updated daily, stored in database
- Used for admin dashboard and worker recognition

### Verification Checklist
- [ ] Toolbox talks generated from aggregated observations
- [ ] Foreman receives coaching prompts with observation context
- [ ] Worker receives confirmation when observation used in toolbox talk
- [ ] Morning nudges sent at correct local time
- [ ] Engagement score calculated correctly
- [ ] All messages comply with sending window (8am-9pm)
- [ ] Can view engagement metrics by worker and company

---

## Phase 5: Admin Portal (Weeks 8-10)

**Priority:** Let companies configure and monitor the platform
**Owner:** Claude Code

### Deliverables

#### Admin Portal Frontend (Astro + Tailwind or React)
- Login & auth integration (company admin role)
- Responsive dashboard
- Dark mode support (brand colors applied)

#### Company Configuration
- Upload safety standards (PDF → stored reference)
- Manage projects (create, edit, archive)
- Add workers (CSV import or manual form)
- Configure message frequency and sending window
- Set default trade and experience level per worker

#### Observation Feed
- Real-time feed of incoming observations
- Filters: date range, hazard type, trade, worker, severity
- Pagination (50 observations per page)
- Mark as reviewed or archived

#### Toolbox Talk Management
- View generated toolbox talks
- Edit before distribution (remove, add points)
- Schedule distribution (scheduled send to foremen)
- View which observations were included

#### Engagement Metrics Dashboard
- Worker engagement scorecards (narrative + metrics)
- Company-wide trends (observation volume, top hazards)
- Response time analytics
- Opt-out tracking and re-engagement prompts
- Export reports (CSV)

#### Worker Management
- View all workers in company
- Deactivate/reactivate workers (consent managed separately)
- Bulk assign to projects
- View worker engagement history

### Verification Checklist
- [ ] Admin login works (test with demo company)
- [ ] Can upload safety standards document
- [ ] Can create project and add 5+ workers
- [ ] Observation feed displays and filters correctly
- [ ] Can edit and schedule toolbox talks
- [ ] Engagement scores display for all workers
- [ ] Metrics dashboard loads in under 3 seconds
- [ ] Report export produces valid CSV

---

## Phase 6: Polish & Launch (Weeks 10-12)

**Priority:** Quality, security, performance, and first customer deployment
**Owner:** Claude Code

### Deliverables

#### End-to-End Testing
- Full workflow: worker opt-in → observation → coaching response → toolbox talk
- Test across all trades and experience levels
- Simulate concurrent users (load test)
- Edge cases: network failures, API timeouts, duplicate messages

#### Security Audit
- Encryption: PII at rest (database) and in transit (TLS)
- Consent enforcement: verify no messages sent without consent
- SQL injection prevention (parameterized queries via SQLAlchemy)
- CSRF protection on admin portal
- API rate limiting (prevent abuse)
- Secrets management (.env, no hardcoded keys)

#### Performance Optimization
- Response time target: under 5 seconds for coaching responses
- Database query optimization (add indexes if needed)
- Cache frequently accessed data (trades, experience levels)
- Async message sending (don't block inbound webhook)

#### Documentation
- API documentation (OpenAPI/Swagger)
- Deployment guide (Railway or Render setup)
- Admin user guide (PDF or in-app help)
- Operations runbook (monitoring, troubleshooting)
- Safety framework reference (behavioral coaching principles)

#### Pilot Deployment
- Deploy to production environment
- Configure with first customer (onboarding process)
- Monitor: error logs, SMS delivery, API latency
- Gather user feedback (admin and workers)
- Fix bugs and iterate

#### Monitoring & Alerting
- Uptime monitoring (status page)
- Twilio API health checks
- Database connectivity monitoring
- SMS delivery success rate tracking
- Error rate alerts (PagerDuty or similar)
- Daily health report (metrics summary)

### Verification Checklist
- [ ] All phases 1-5 verified and working
- [ ] No critical security vulnerabilities found
- [ ] Coaching response time consistently under 5 seconds
- [ ] End-to-end test passes (full workflow)
- [ ] First customer successfully onboarded
- [ ] Production monitoring active
- [ ] Documentation complete and reviewed
- [ ] Team trained on operations

---

## Build Rules for Claude Code

**Execute these rules on every implementation:**

1. **Build & Test One Component at a Time**
   - Complete and test one feature before starting the next
   - Do not stack incomplete work

2. **Write Tests Alongside Implementation**
   - Unit tests for all business logic
   - Integration tests for SMS flows
   - Use pytest with fixtures
   - Minimum 80% code coverage for Phase 2+

3. **Use Plan Mode for Complex Features**
   - If a feature touches 3+ files, write a detailed plan first
   - Get verification before implementation
   - Prevents rework and ensures quality

4. **Commit After Each Working Feature**
   - Atomic commits with clear messages
   - Example: `feat: add consent verification logic`
   - Enables rollback if needed

5. **Never Skip SMS Compliance Checks**
   - Every outbound message must verify consent first
   - Respect opt-out keywords (case-insensitive)
   - Enforce sending window (8am-9pm recipient timezone)
   - Log all transactions
   - No exceptions to these rules

6. **Reference Documentation When Uncertain**
   - Behavioral coaching decisions → `docs/BEHAVIORAL_FRAMEWORK.md`
   - Brand voice and color questions → `docs/BRAND_GUIDE.md`
   - SMS compliance details → `docs/SMS_COMPLIANCE.md`
   - Never invent guidance; reference docs

7. **Use Brand Guide for Frontend**
   - All web pages use Amber/Slate/Concrete color palette
   - All text uses DM Sans (headings) and Inter (body)
   - Consistent spacing and typography across all pages

8. **Log Everything**
   - All SMS transactions (inbound, outbound, opt-out)
   - All API calls to Claude and Twilio
   - All database changes (audit trail)
   - Use structured logging (JSON format)

9. **Environment Isolation**
   - Development: local SQLite, test Twilio account
   - Staging: production database snapshot, test Twilio numbers
   - Production: production Twilio, encrypted secrets
   - Never run production code against dev data

10. **Security First**
    - All user inputs validated and sanitized
    - No PII in logs or error messages
    - Secrets never committed to version control
    - Rate limiting on all public endpoints
    - HTTPS only for all web pages

---

## Success Criteria

By end of Week 12, the platform will:
- Deliver intelligent safety coaching via SMS in 5 seconds
- Maintain 100% SMS compliance (consent, opt-out, timing)
- Close the feedback loop (observations → toolbox talks → confirmation)
- Provide admin controls for company configuration and monitoring
- Support first pilot customer with zero downtime
- Be ready for scaled rollout to additional customers

---

## Timeline Overview

| Phase | Weeks | Deliverable | Owner |
|-------|-------|-------------|-------|
| 1 | 1-2 | Website, Twilio account, campaign approval | Claude Code |
| 2 | 2-4 | FastAPI backend, database, SMS handling | Claude Code |
| 3 | 4-6 | Coaching engine, trade calibration, Claude API | Claude Code |
| 4 | 6-8 | Toolbox talks, foreman coaching, engagement scoring | Claude Code |
| 5 | 8-10 | Admin portal, company config, metrics dashboard | Claude Code |
| 6 | 10-12 | Testing, security, optimization, pilot launch | Claude Code |

---

## Next Steps (Claude Code)

1. Set up GitHub repository
2. Create project board (GitHub Projects or Linear)
3. Create `.env.example` and `.env` for development
4. Begin Phase 1: Website design and Twilio account setup
5. Post weekly progress updates to project board
