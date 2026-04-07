# Safety as a Contact — Project Status

**Last updated:** March 27, 2026
**Owner:** Travis Sparks (bryantravissparks@gmail.com / travis@safetyasacontact.com)

---

## What This Project Is

SMS-based workplace safety coaching for construction workers. Workers text photos and descriptions of jobsite hazard observations to a dedicated phone number. An AI system responds with references from the company's actual safety documents (site safety plans, OSHA standards, incident reports, lessons learned) and asks behavioral reflection questions. The AI never gives technical safety advice, never implies trade expertise, and never tells workers what to do. It surfaces documents and asks questions — that's it.

The product serves companies in the 50-250 employee range who may not have mature safety programs or sophisticated safety technology.

---

## Business Entity

- **Legal Name:** BRYAN TRAVIS SPARKS (sole proprietor)
- **DBA:** Safety as a Contact
- **EIN:** 41-4833988
- **Address:** 2730 E STANFORD LN, HOLLADAY, UT 84117
- **IRS CP-575G:** On file at `CP_575_G (1).pdf` in project root
- **Domain:** safetyasacontact.com (registered via Squarespace)
- **Email forwarding:** travis@, support@, privacy@ → bryantravissparks@gmail.com (set up via Squarespace, may need DNS propagation time)

---

## Architecture Summary

### The Pivot (completed)

The project underwent a major architectural pivot from an "AI coaching engine that generates technical safety advice" (liability risk) to a "document-grounded reference system that surfaces uploaded documents and asks reflective questions" (zero liability).

**Three response modes:**
1. **ACKNOWLEDGE + REFERENCE** — Surface a specific document section with attribution
2. **ACKNOWLEDGE + REFLECT** — Ask a behavioral, non-technical question
3. **ACKNOWLEDGE + CONNECT** — Bridge when observation is outside worker's usual trade area

**Hard liability rules (100% enforced, validated):**
- AI never evaluates safety of setups
- AI never provides engineering advice
- AI never implies trade knowledge
- AI never tells workers what to do
- AI never uses first-person constructions ("I can see...", "I notice...")
- 57 prohibited phrases enforced
- All factual references attributed to specific documents

**Pivot plan:** `project/docs/PIVOT_PLAN.md`

### Tech Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, SQLite (dev) / PostgreSQL (prod)
- **AI:** Claude Haiku (claude-haiku-4-5-20251001), temperature 0.3, max 500 tokens
- **SMS:** Telnyx (migrated from Twilio) — REST API via httpx
- **Frontend/Landing:** Astro static site at safetyasacontact.com
- **Testing:** pytest, 205 tests passing

### Key Files

| File | Purpose |
|------|---------|
| `backend/coaching/prompts.py` | All prompt blocks, response modes, prohibited phrases, build_system_prompt() |
| `backend/coaching/engine.py` | Coaching pipeline: session mgmt → doc retrieval → Claude API → profile update |
| `backend/coaching/profile.py` | Worker profiles, tier calculation (photo-weighted), mentor notes |
| `backend/coaching/trades.py` | 12 construction trades with hazard profiles |
| `backend/documents/retrieval.py` | Keyword-based document search with Spanish→English expansion (56 terms) |
| `backend/documents/ingestion.py` | PDF/text document chunking by section, trade/hazard tagging |
| `backend/documents/pdf_extractor.py` | PDF text extraction with header/footer stripping |
| `backend/documents/insights.py` | Aggregated observation insight generation (social feedback loop) |
| `backend/sms/handler.py` | Telnyx inbound webhook + core message routing |
| `backend/sms/sender.py` | Telnyx outbound SMS via REST API |
| `backend/sms/consent.py` | Double opt-in consent management |
| `backend/sms/compliance.py` | Sending window (8am-9pm), rate limits (5/day) |
| `backend/models.py` | 12 SQLAlchemy tables including SafetyDocument, DocumentReference, WorkerProfile, InteractionAssessment |
| `backend/config.py` | Environment config (Telnyx, Anthropic, database, compliance settings) |
| `backend/api/documents.py` | REST endpoints for document upload/search/list |
| `scripts/ingest_wollam_docs.py` | Ingests real Wollam PDFs into document database |

### Database Tables

Core: Company, Project, Worker, ConsentRecord, CoachingSession, Observation, CoachingResponse, MessageLog
Pivot additions: WorkerProfile, InteractionAssessment, SafetyDocument, DocumentReference

---

## What's Been Built and Validated

### Phase 1-5: Architectural Pivot (COMPLETE)
- Prompt architecture rebuilt (identity, response modes, reflection blocks, document context injection)
- Coaching engine integrated with document retrieval
- Worker profile system with photo-weighted tier calculation
- Database schema expanded (3 new tables, 4 updated tables)
- Document retrieval system (keyword matching, category priority, trade filtering)
- Document ingestion with section chunking
- Spanish→English keyword expansion (56 safety terms)
- 205 unit/integration tests passing

### Validation Results (ALL PASSING)
- **Single-turn (10 scenarios):** 10/10 hard rule pass, 100% question rate, 100% name usage, 80% word count
- **Multi-turn (3 conversations, 13 turns):** 13/13 hard rule pass, session continuity confirmed, thread awareness working, document variety confirmed
- **Real documents (10 scenarios with Wollam/Valar PDFs):** 10/10 hard rule pass, responses cite real company documents with proper attribution
- **315 document sections ingested** from 2 real PDFs (169 from Wollam Safety Program, 146 from Valar Ward 250 SSSP)

### Prompt Tuning (COMPLETE)
- Brevity target tightened: 25-40 words max, "Two sentences. One to acknowledge, one to ask."
- Sentence-boundary truncation at 380 chars (replaces hard 320-char slice)
- Name usage: always on turn 1, then every 3-4 responses
- All soft criteria hitting targets after tuning

### SMS Migration: Twilio → Telnyx (COMPLETE)
- All SMS code rewritten for Telnyx REST API (no SDK dependency)
- Webhook handler accepts Telnyx JSON format
- MMS photo download to local storage (Telnyx URLs are ephemeral)
- Webhook signature validation via ed25519
- Config updated: 4 Telnyx env vars replace 4 Twilio vars
- All tests updated and passing (205 total)

### Landing Page (COMPLETE)
- Privacy policy with TCR-compliant SMS opt-in data sharing clause
- SMS Terms & Conditions
- Terms of Service
- Consent form with double opt-in
- All pages reference Telnyx (not Twilio)

### Telnyx Account Setup (IN PROGRESS)
- Account created and funded ($9.98)
- Upgraded to Paid tier
- Phone number purchased: +18013163196 (Utah 801)
- Messaging profile configured
- KYC identity verification submitted — **waiting for approval**
- Brand and campaign registration prepped but blocked on KYC

---

## Documents Created This Session

| File | Purpose |
|------|---------|
| `docs/PIVOT_PLAN.md` | Comprehensive pivot plan (from prior session, still the source of truth) |
| `docs/WHITE_LABEL_LIBRARY.md` | Product brief for future OSHA/MSHA default document library |
| `docs/SMS_PROVIDER_RESEARCH.md` | Telnyx research: pricing, compliance, integration architecture |
| `docs/TELNYX_MIGRATION_PROMPT.md` | Claude Code prompt used for the Twilio→Telnyx swap |
| `docs/TELNYX_10DLC_REGISTRATION.md` | Exact brand/campaign registration details from CP-575G |
| `tests/test_pivot_integration.py` | 24 integration tests: doc retrieval, pipeline, response quality, tier calc |
| `tests/live_validation.py` | 10-scenario single-turn live API validation |
| `tests/live_multiturn_validation.py` | 3-conversation multi-turn live API validation |
| `tests/live_real_docs_validation.py` | 10-scenario validation against real Wollam documents |
| `backend/documents/pdf_extractor.py` | PDF text extraction utility |
| `scripts/ingest_wollam_docs.py` | Real document ingestion script |

---

## What's Next (Priority Order)

### Immediate (blocked on Telnyx)
1. **KYC approval** → then brand registration → campaign registration → webhook wiring
2. **First live SMS test:** Text a photo to +18013163196 and get a real coaching response back
3. **End-to-end verification:** STOP/START/HELP keyword handling, MMS photo download, consent flow

### Short-term
4. **Real pilot planning:** Pick a Wollam project, select 5-10 workers, run a controlled test
5. **Admin interface:** Simple web UI for safety directors to upload documents (currently requires running a script)
6. **Social feedback loop:** Wire up the observation insight generation (code exists in `insights.py`, needs scheduler/admin toggle)

### Medium-term
7. **White-label OSHA document library:** 15-20 plain-language safety documents as defaults for companies without their own (product brief at `docs/WHITE_LABEL_LIBRARY.md`)
8. **Dashboard:** Safety director view showing worker engagement, document usage, observation trends
9. **Evaluation pipeline rebuild:** Update the 7-agent evaluation system for new response modes

### Future
10. **MSHA library expansion** (mining operations)
11. **Multi-company infrastructure** (company isolation, billing, onboarding)
12. **Mobile app** (if SMS proves limiting)

---

## Key Decisions Made

1. **AI never gives technical advice.** This is the foundational product decision. The system surfaces documents and asks questions. Period.
2. **Document-grounded, not knowledge-grounded.** Every factual reference comes from an uploaded document with attribution. The AI's training data is never the source of truth.
3. **Telnyx over Twilio.** Half the cost, better support, faster campaign approvals, licensed carrier.
4. **Sole proprietor for now.** LLC planned when revenue starts. DBA keeps brand name flexible.
5. **MVP uses keyword matching, not vector embeddings.** PostgreSQL full-text search is sufficient for the document sizes we're working with. Vectors are a future optimization.
6. **Photo-weighted tier calculation.** Replaced "text length" with "photo consistency" so workers like Miguel who send photos with minimal text can still progress.
7. **Spanish keyword expansion in retrieval layer.** Documents will always be English. The system bridges Spanish observations to English documents via a 56-term lookup table.

---

*This document is the single source of truth for project status. Update it at the start of each major work session.*
