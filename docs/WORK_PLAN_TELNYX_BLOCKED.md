# Safety as a Contact — Work While Telnyx Is Blocked

## Context

Telnyx account is blocked (KYC verification issue), so no live SMS testing. But the coaching engine, eval pipeline, deployment, and document retrieval are all independent of SMS delivery. This plan covers 6 tasks that advance the product while waiting for Telnyx resolution.

## Critical Discovery

The main database (`safety_as_a_contact.db`) has the `safety_documents` table schema (created by `init_db()` → `Base.metadata.create_all()` on app startup), but the table is **empty**. The 315 Wollam doc sections were ingested into a separate `data/wollam_docs.db` because the ingestion script defaults to that path. The coaching engine queries the main DB via `backend/documents/retrieval.py`, so document retrieval returns nothing. Fix: re-run ingestion with `--db-path safety_as_a_contact.db`.

---

## Task 1: Commit Uncommitted Work (~20 min)

28 modified files + 23 untracked files. Split into 4 logical commits.

**Pre-commit:** Add `.coverage` and `training_reports/` to `.gitignore`.

**Commit 1 — feat: migrate SMS provider from Twilio to Telnyx REST API**

Files:
- `backend/config.py` (Telnyx settings replace Twilio)
- `backend/sms/handler.py` (Telnyx webhook format + ed25519 signature validation)
- `backend/sms/sender.py` (Telnyx REST API via httpx)
- `backend/models.py` (any SMS-related model changes)
- `.env.example` (Telnyx env vars)
- `requirements.txt` (removed twilio, added PyMuPDF — see note below)
- `site/src/pages/consent.astro` (Telnyx phone number)
- `site/src/pages/privacy.astro` (Telnyx references)
- `site/.gitignore`
- `tests/conftest.py`, `tests/test_sms_handler.py`, `tests/test_integration.py`
- `docs/SMS_PROVIDER_RESEARCH.md`, `docs/TELNYX_10DLC_REGISTRATION.md`, `docs/TELNYX_MIGRATION_PROMPT.md`

**Commit 2 — feat: add training evaluation pipeline with quality gate**

Files:
- `training/__init__.py`, `training/models.py`, `training/db.py`
- `training/scoring.py`, `training/catalog.py`, `training/compare.py`
- `training/benchmark.py`, `training/analyze.py`, `training/review.py`
- `training/__main__.py` (NEW — CLI entry point)
- `training/quality_gate.py` (NEW)
- `training/report.py` (NEW)
- `training/evaluators/__init__.py` (NEW)
- `training/evaluators/base.py` (NEW)
- `training/evaluators/arc_eval.py` (NEW)
- `training/evaluators/authenticity_eval.py` (NEW)
- `training/evaluators/behavioral_eval.py` (NEW)
- `training/evaluators/hazard_eval.py` (NEW)
- `backend/api/training.py`, `backend/templates/training.html`

**Commit 3 — feat: add multi-turn simulation with worker personas**

Files:
- `training/simulator.py` (NEW — multi-turn conversation simulator)
- `training/worker_ai.py` (NEW — worker persona AI)
- `training/personas.py` (NEW — 4 personas: Miguel, Jake, Ray, + others)
- `backend/templates/simulations.html` (NEW)
- `tests/test_coaching_engine.py`, `tests/test_worker_profile.py`
- `backend/coaching/profile.py`
- `backend/templates/console.html` (persona quick-select)

**Commit 4 — docs: add project status and pivot documentation**

Files:
- `docs/PROJECT_STATUS.md` (NEW)
- `docs/PIVOT_PLAN.docx` (NEW)
- `docs/WHITE_LABEL_LIBRARY.md` (NEW)

**IMPORTANT:** Before committing, add `PyMuPDF` to `requirements.txt`. It is imported in `backend/documents/pdf_extractor.py` but missing from requirements. This will break deployment and any fresh install. Add the line:

```
PyMuPDF>=1.24.0
```

**Verify:** `pytest tests/ -q` passes after each commit.

---

## Task 2: Improve Document Retrieval Quality (~30 min)

Do this BEFORE running evals so the baseline scores reflect clean document data.

### Step 2a: Add minimum section length filter

File: `backend/documents/ingestion.py` — in `ingest_document()`, skip sections with `len(content.strip()) < 80` characters. These are fragments (bare headings, partial sentences) that add noise to retrieval.

### Step 2b: Tighten section heading detection

File: `backend/documents/ingestion.py` — in `_split_into_sections()`, change the heading regex from `r'^(\d+[\.\d]*\.?\s+\S.*)$'` to require X.Y format (e.g., `1.0`, `3.2`) instead of matching bare numbers like `3.`. This prevents splitting on numbered list items.

### Step 2c: Tighten heading join heuristic

File: `backend/documents/pdf_extractor.py` — in `_join_split_section_numbers()`, reduce max heading length from 200 to 80 chars, and exclude lines ending in `.` (these are sentences, not headings).

### Step 2d: Re-ingest and verify

```bash
python -m scripts.ingest_wollam_docs
```

Compare section counts before/after. Expect fewer sections with higher average content quality.

**Verify:** Fewer total sections than 315. Spot-check that remaining sections contain substantive content, not fragments.

---

## Task 3: Fix Document DB + Run Eval Pipeline (~20 min)

### Step 3a: Re-ingest documents into main DB

The `safety_documents` table already exists in the main DB (created by `init_db()`), it's just empty. Point the ingestion script at it:

```bash
python -m scripts.ingest_wollam_docs --db-path safety_as_a_contact.db
```

**Verify:** Query the main DB to confirm sections were ingested. The count should match the improved ingestion from Task 2.

### Step 3b: Run quality gate

```bash
python -m training gate --sessions 10 --prompt-version "post-pivot-v1"
```

This runs 3 personas (miguel, jake, ray) × 10 sessions × 4 turns each = ~120 coaching responses, all via Claude Haiku API. Estimated cost: ~$0.50–1.00.

The `gate` subcommand in `training/__main__.py` is confirmed wired up. It calls `_run_gate()` which iterates over personas, runs simulation + evaluation, then prints a summary.

### Key thresholds to watch

| Category | Metric | Required |
|---|---|---|
| Compliance | word_count 25–50w | 100% |
| Compliance | no_first_person | 100% |
| Compliance | no_safety_judgments | 100% |
| Response Quality | question_ratio | >75% |
| Response Quality | document_grounding | >3.0 |
| Behavioral Science | composite | >3.5 |
| Authenticity | sounds_human | >3.5 |

**Verify:** Terminal output shows per-persona scorecard. JSON reports saved to `training_reports/`.

---

## Task 4: Prompt Tuning (~1–2 hours, iterative)

File: `backend/coaching/prompts.py`

Based on eval results from Task 3, iterate on the system prompt. Likely tuning areas:

- **Word count too long:** Tighten BREVITY_BLOCK, add hard-limit reinforcement
- **Question ratio < 75%:** Move QUESTION_BLOCK earlier, add final-check instruction
- **Spanish quality:** Strengthen LANGUAGE_BLOCK_ES with concrete examples
- **Document grounding low:** Strengthen attribution instructions in doc context block
- **Safety judgments leaking:** Add more examples to prohibition list

### Iteration loop

1. Read quality gate JSON — identify failing checks
2. Read raw responses in transcript to understand what the model produces
3. Modify `prompts.py`
4. Re-run: `python -m training gate --sessions 5 --prompt-version "post-pivot-v2"`
5. Compare reports, repeat until PASS or CONDITIONAL_PASS

**Verify:** Quality gate report shows PASS or CONDITIONAL_PASS for all categories.

---

## Task 5: Update CLAUDE.md + Docs (~30 min)

File: `CLAUDE.md` — full rewrite needed. Current version has stale references:

- Twilio → Telnyx throughout
- 5 response modes (Alert, Validate, Nudge, Probe, Affirm) → 3 modes (reference/reflect/connect)
- Port 8000 → 8002
- 48 tests → 205+
- Project structure: add `coaching/`, `documents/`, `training/`
- Add document-grounded coaching architecture section
- Remove Twilio skill reference, add Telnyx details

File: `docs/ARCHITECTURE.md` — update SMS provider, response modes, system prompt description.

**Verify:** `grep -i "twilio" CLAUDE.md` returns zero matches. `grep -i "alert.*validate.*nudge" CLAUDE.md` returns zero matches.

---

## Task 6: Deploy Backend to Render (~1 hour)

### Step 6a: Create deployment files

Create `Procfile` in project root:

```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Step 6b: Add CORS middleware

File: `backend/main.py` — after `app = FastAPI(...)`, add:

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://safetyasacontact.com",
        "https://www.safetyasacontact.com",
        # Add Render URL after deploy
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Do NOT use `allow_origins=["*"]`. Lock to actual domains.

### Step 6c: Add demo mode for console access in production

File: `backend/config.py` — add `demo_mode: bool = False`

File: `backend/main.py` — change production guards:

```python
if settings.is_production and not settings.demo_mode:
    return HTMLResponse(status_code=404, content="Not found")
```

### Step 6d: Database — use Neon (free tier, serverless PostgreSQL)

Create via Neon dashboard or MCP tools. Connection string format is standard PostgreSQL, works directly with SQLAlchemy.

### Step 6e: Deploy to Render

- Connect GitHub repo, set build command (`pip install -r requirements.txt`) and start command (from Procfile)
- Set env vars: `ENVIRONMENT=production`, `DATABASE_URL`, `ANTHROPIC_API_KEY`, `SECRET_KEY`, `PHONE_HASH_SALT`
- Telnyx vars can be placeholders until account is resolved
- Set `DEMO_MODE=true` for console access

### Step 6f: Ingest documents into production DB

Run ingestion script locally with `DATABASE_URL` pointed at Neon PostgreSQL:

```bash
DATABASE_URL="postgresql://..." python -m scripts.ingest_wollam_docs --db-path ""
```

(The script will need a small modification to respect `DATABASE_URL` env var instead of `--db-path` for PostgreSQL. Alternatively, add a `--use-env-db` flag.)

**Verify:** `curl https://<app>.onrender.com/health` returns OK. Console loads and produces coaching responses with document citations.

---

## Deferred: Photo Storage with Supabase

**Why deferred:** MMS photo flow requires Telnyx to be working end-to-end. Local file storage works for dev, and there are no production users yet. Implement this after Telnyx KYC is resolved and you can test the full SMS → photo download → storage → coaching pipeline.

When ready, the scope is:
- Create `backend/storage.py` — dual-mode (Supabase in prod, local filesystem in dev)
- Modify `backend/sms/handler.py` `_download_media()` to use `storage.py`
- Add `supabase>=2.0.0` to `requirements.txt`
- Create Supabase storage bucket `observations` with public access

---

## Execution Order

```
Task 1 (Commit) ──→ Task 2 (Doc Quality) ──→ Task 3 (Fix DB + Eval) ──→ Task 4 (Prompt Tuning)
                                                                              │
                                                                              ▼
                                                                         Task 5 (Update Docs)
                                                                              │
                                                                              ▼
                                                                         Task 6 (Deploy)
```

**Recommended sequence: 1 → 2 → 3 → 4 → 5 → 6**

Rationale:
- Task 2 before Task 3 so eval baseline reflects clean document data
- Task 5 after Task 4 so CLAUDE.md captures final prompt state
- Task 6 last because it deploys the finished, tested, documented product
- Photo storage deferred until Telnyx is live

---

## Key Files

| File | Tasks |
|---|---|
| `backend/coaching/prompts.py` | 4 |
| `backend/coaching/engine.py` | 4 |
| `backend/sms/handler.py` | 1 |
| `backend/main.py` | 6 |
| `backend/config.py` | 6 |
| `backend/documents/ingestion.py` | 2 |
| `backend/documents/pdf_extractor.py` | 2 |
| `scripts/ingest_wollam_docs.py` | 2, 3 |
| `training/__main__.py` | 3, 4 |
| `CLAUDE.md` | 5 |
| `requirements.txt` | 1 (add PyMuPDF) |
| `Procfile` (new) | 6 |
| `.gitignore` | 1 (add .coverage, training_reports/) |
