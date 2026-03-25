# Safety as a Contact — Architectural Pivot Plan

**Date:** March 24, 2026
**Context:** This document is the source of truth for a major architectural pivot. It is written for Claude Code to execute. Read this entire document before making any changes.

---

## Why We Are Pivoting

The current coaching engine produces responses that sound like a knowledgeable construction peer. In testing, Jake's coaching transcript scored 4.80/5.0 on trade credibility — the AI discusses sling angles, load distribution, bearing surfaces, and tag line geometry with apparent authority. That is the problem.

The AI does not possess trade knowledge. It generates statistically plausible text from language model training. When a worker trusts that voice the way they'd trust a twenty-year foreman, we've created a dangerous dependency. A rigging decision made on the strength of an AI response that happened to sound authoritative is a liability this project cannot carry.

The core issue: there is a difference between **empowering a worker to think** and **telling a worker what to do**. The product vision describes peer coaching, but the transcripts show the system drifting toward advisory — making engineering judgments, evaluating rigging setups, assessing soil stability. The pivot corrects that drift.

### The New Model

The system becomes two distinct layers with a hard boundary between them:

1. **Document layer** — A safety professional uploads the company's safety knowledge base. This goes well beyond just policies and OSHA standards. The document library includes:

   - **Site safety plans** — project-specific requirements from the contract documents
   - **Company safety procedures** — the company's own rules and standards
   - **OSHA/MSHA standards** — industry regulations relevant to the project scope
   - **Incident reports** — real incidents from the company's history, documented with what happened, what went wrong, and what was learned. When a worker photographs a grinder on a table, the system can surface a real incident where someone at the same company was injured using a grinder without a guard. The authority isn't AI — it's the company's own experience.
   - **Lessons learned** — post-incident analyses, near-miss summaries, safety bulletins, toolbox talk archives. The accumulated wisdom of the organization, made searchable and deliverable at the point of work.
   - **Hazard registers** — active hazard observation logs, recurring issues, known problem areas on the current project. When a worker photographs something that's already on the hazard register, the system can say so.
   - **Trade-specific references** — pre-built safety references for each of the 12 supported trades
   - **Observation insight reports** (system-generated) — aggregated summaries of worker observations across projects and the company. These are not uploaded by a human — they are generated periodically from the observation database and published into the document layer, gated by a safety director toggle. See "Social Feedback Loop" section below for details.

   When a worker sends a photo, the system retrieves relevant sections from these uploaded documents and returns attributed snippets. The AI is a librarian, not an expert. The source is always cited.

   This is where the product's value proposition becomes significantly stronger than a generic safety app. A regulation tells a worker what the rule is. An incident from their own company tells them *why the rule exists* — because someone like them, on a job like theirs, got hurt. That institutional memory doesn't currently have a delivery mechanism that reaches workers at the point of work. This system creates one.

2. **Behavioral reflection layer** — The AI asks one open-ended question that prompts the worker to think or act. No technical authority. No engineering judgment. No directive language. Just: "Who else needs to see this?" "Has this come up before?" "What's your next move?" These questions carry zero liability because they contain zero technical content.

3. **Social feedback layer** — The system surfaces aggregated observation data back to workers, creating visibility into how the tool is being used across the company and what patterns are emerging. When a worker reports an unguarded trench and the system knows that similar observations have been submitted by other workers across multiple job sites, it can say so: "This is the seventh open trench observation across the company this month. Sounds like this is a pattern worth surfacing." The authority is the collective input of the workforce, not the AI's judgment. See "Social Feedback Loop" section below.

The AI never generates technical advice from its own training. It only surfaces content from documents that real professionals wrote and uploaded, aggregated observation data from other workers, and asks reflective questions that connect workers to their own knowledge.

### What This Is NOT

- NOT a chatbot that pretends to know construction trades
- NOT a compliance officer citing regulations
- NOT an advisory system that evaluates whether setups are safe
- NOT a replacement for on-site supervision or professional judgment

### What This IS

- A document delivery system that makes safety plans accessible at the point of work via SMS
- A behavioral reflection engine that helps workers develop their own observational judgment
- A worker profile system that tracks cognitive and behavioral development over time
- A research-grade insight tool for safety professionals

---

## Architecture Overview

### Current Flow (Being Changed)
```
Worker sends photo/text
  → Coaching Engine builds system prompt with trade-expert persona
  → Claude generates response as "experienced construction professional"
  → Response contains technical advice, engineering judgments, trade-specific guidance
  → Worker profile updated, response sent via SMS
```

### New Flow (Target State)
```
Worker sends photo/text
  → System identifies hazard category and trade context from photo/message
  → Document Retrieval queries uploaded safety documents for relevant sections
  → Coaching Engine builds system prompt with:
      - Retrieved document snippets (attributed to source)
      - Worker's trade and profile context
      - Behavioral reflection rules (no technical authority)
  → Claude generates response:
      - Acknowledges what the worker sent
      - References relevant document content (if found), attributed to source
      - Asks one reflective question (no technical content)
  → Document references logged, worker profile updated, response sent via SMS
```

---

## What Stays Unchanged

These components carry forward with zero or minimal modifications:

| Component | File(s) | Notes |
|-----------|---------|-------|
| SMS inbound/outbound pipeline | `backend/sms/handler.py`, `backend/sms/sender.py` | Twilio webhooks, message routing, outbound delivery |
| Consent system | `backend/sms/consent.py` | Double opt-in, opt-out, TCPA compliance |
| Compliance layer | `backend/sms/compliance.py` | 8am-9pm sending window, 5 msgs/day rate limit |
| Session management | `backend/coaching/engine.py` — `get_or_create_session()`, `get_thread_history()`, `update_session_metadata()` | 4-hour timeout, turn counting, thread history |
| Trade matching | `backend/coaching/trades.py` | 12 trades, fuzzy matching, experience calibration |
| Database tables | `backend/models.py` | All 10 existing tables stay. New tables are additive. |
| Photo handling | `backend/coaching/prompts.py` — `build_user_message()`, `_resolve_local_image()` | Base64 encoding, Claude Vision content blocks |
| Config and database setup | `backend/config.py`, `backend/database.py` | Environment variables, SQLAlchemy engine |
| API endpoints | `backend/api/health.py`, `backend/api/console.py` | Health check, test console |
| FastAPI app | `backend/main.py` | Router wiring, startup |

---

## What Changes

### 1. Prompt Architecture (`backend/coaching/prompts.py`)

This is the biggest change. The entire system prompt is rebuilt around the document-grounded + reflective model.

#### REMOVE These Blocks

**`IDENTITY_BLOCK`** (lines 52-85) — The "20+ years construction professional" persona. This is the root of the liability problem. It positions the AI as having trade expertise it doesn't possess. Every line that says "seasoned," "experienced," "knows the craft," "from the field" must go.

**`MODE_BLOCK`** (lines 90-106) — The five coaching modes (ALERT, VALIDATE, NUDGE, PROBE, AFFIRM). These are designed around the AI making its own judgments about hazard severity and coaching approach. Replace with the new three-mode system described below.

**`TIER_INSTRUCTIONS`** (lines 111-128) — The tier-adapted coaching that says things like "challenge their thinking" and "peer-level exchange." The new tier system adapts the *reflection style*, not the *technical depth* of coaching.

**`CLASSIFICATION_PROMPT`** (lines 276-305) — The "construction safety classifier" prompt. Replace with a lighter classifier that identifies observation context for document retrieval, not for the AI to make safety judgments.

**All mock response templates** in `engine.py` — `_MOCK_RESPONSES`, `_MOCK_PHOTO_RESPONSES`, `_MOCK_NO_PHOTO_RESPONSES` (lines 229-280). Rewrite to match the new response model.

#### KEEP These Blocks (With Modifications Noted)

**`PROHIBITED_PHRASES`** (lines 11-47) — Keep the full list. Add new prohibitions:
- "That setup looks unsafe"
- "That's a hazard"
- "That needs to be fixed"
- "You need to"
- Any language that implies the AI is making a safety judgment
- Any language that implies the AI has trade-specific knowledge

**`ACKNOWLEDGMENT_BLOCK`** (lines 222-243) — Keep as-is. The acknowledge-before-responding pattern is central to the new model.

**`QUESTION_BLOCK`** (lines 208-219) — Keep as-is. Every response must contain a question mark. This is even more important in the new model since the reflective question IS the product.

**`BREVITY_BLOCK`** (lines 188-205) — Keep the 25-50 word target. Update examples to reflect the new response model (document reference + reflective question instead of coaching observation + probe).

**`LANGUAGE_BLOCK_ES`** (lines 246-269) — Keep the Spanish voice requirements. Update examples to match the new response model. The Spanish must still sound like a real person, not a translated bot — that requirement is unchanged.

**`LANGUAGE_BLOCK_EN`** (lines 271-273) — Keep as-is.

**`TURN_GUIDANCE`** (lines 133-183) — Keep the structure but rewrite content. Turn 1 still gathers context. Middle turns still go deeper or broader. Closing turns still read the energy. But the guidance must reflect document-grounded responses, not AI-generated coaching.

**`build_system_prompt()`** function (line 308) — Keep the function signature and assembly pattern. Change the blocks it assembles and add new parameters for document context.

**`build_user_message()`** function — Keep as-is. Photo handling doesn't change.

#### ADD These New Blocks

**`IDENTITY_BLOCK_V2`** — New identity. The AI is a resource assistant that connects workers to their project's safety documentation and asks reflective questions. It has NO trade expertise. It never evaluates whether a setup is safe. It never provides engineering advice. It acknowledges what the worker sent, surfaces relevant documentation if it exists, and asks one question that connects the worker to their own knowledge and the people around them on site.

Key rules for the new identity:
- Never say "that looks unsafe" or make any safety judgment
- Never imply trade-specific knowledge ("that bearing surface," "those sling angles")
- Never tell a worker what to do — only ask what they think or who they've talked to
- When referencing documents, always attribute: "Your site safety plan says..." or "Per [document name]..."
- When no document covers the observation, say so honestly: "Nothing in the current site documents covers this specifically — worth flagging to your supervisor."
- The no-first-person rule remains absolute

**`DOCUMENT_CONTEXT_BLOCK`** — Dynamically injected per-response. Contains 1-3 relevant document snippets retrieved from the document database. Format:

```
REFERENCE DOCUMENTS (use these to ground your response):
The following excerpts are from this project's uploaded safety documentation.
When relevant, quote or paraphrase from these sources and attribute them.
Do NOT generate safety advice beyond what these documents say.
If none of these excerpts are relevant to what the worker sent, say so.

[Source: {document_title} — {section_label}]
{document_content_snippet}

[Source: {document_title} — {section_label}]
{document_content_snippet}
```

If no documents are found, the block should say:
```
No uploaded safety documents match this observation. Do NOT generate safety
advice from your own training. Acknowledge what the worker sent, ask a
reflective question, and suggest they flag it to their supervisor if appropriate.
```

**`REFLECTION_BLOCK`** — Rules for the behavioral reflection question. This is the core of what the AI actually does on its own (as opposed to surfacing documents):

```
YOUR QUESTION MUST BE REFLECTIVE, NOT TECHNICAL.

Good reflective questions:
- "Who else needs to see this?"
- "Has this come up before on this site?"
- "What's your next move?"
- "Did you talk to anyone about it?"
- "How does this connect to the work your crew is doing today?"
- "What would you tell a new guy about this area?"

Bad questions (technical/advisory — NEVER ask these):
- "What's the load capacity on those slings?"
- "Is that shoring adequate for the soil type?"
- "Are those guardrails up to code?"
- "What's the wind speed rating for that crane?"

The question should make the worker THINK or ACT —
not test their knowledge or imply the AI knows the answer.
```

**`NAME_BLOCK`** — The system collects the worker's first name during onboarding or consent flow. When the name is available, use it occasionally — not every response, but roughly 1 in 3 or 1 in 4 interactions. A person's name is the most personal signal in any communication. Using it periodically makes the interaction feel human and recognized, not automated.

```
WORKER NAME USAGE:
The worker's name is: {worker_name}

Use their name occasionally — roughly once every 3-4 responses. NOT every time.
Drop it naturally into acknowledgments or reflective questions:
- "Good eye, Miguel. Who else on your crew has seen this?"
- "Jake, that's the third time you've flagged guardrails this month."
- "Got your photo, Carlos. How does this connect to the pour work today?"

Do NOT:
- Use their name in every response (feels robotic and forced)
- Use their name when delivering document references (keeps the reference neutral)
- Use their name in a way that sounds like a sales script

If no name is available, skip this entirely. Never use "friend," "buddy," or
any substitute. Just drop the name element and respond normally.
```

**`PERSONALIZATION_BLOCK`** — Trade-aware and project-aware response rules. The system knows the worker's trade, experience level, and current project assignment. All three shape how responses are personalized and which documents are retrieved.

```
WORKER CONTEXT:
This worker's trade is {trade} ({experience_level}).
Current project: {project_name}
{project_context if available — e.g., "Commercial pump station, active excavation and underground utilities"}

TRADE-AWARE PERSONALIZATION:
If the observation matches their trade:
  Reference their trade context naturally. "Got your photo of that formwork"
  (to a carpenter). The document retrieval will pull trade-relevant references.

If the observation does NOT match their trade:
  Be honest about the mismatch and use it as a reflection point.
  Example: Worker is a carpenter, sends photo of an excavation.
  Response: "Got your photo of that excavation. How does this connect
  to the framing work you're doing nearby — anything about the layout
  that affects your crew's access?"

  Do NOT pretend to have expertise in the observed trade.
  Do NOT analyze the observation as if you know that trade.
  Ask how it relates to THEIR work.

PROJECT-AWARE PERSONALIZATION:
Document retrieval is scoped to this worker's current project first.
The site safety plan, hazard register, and observation insights are
project-specific. When referencing these, name the project naturally:
  "The pump station safety plan covers fall protection in Section 3.4."
  "There have been six housekeeping observations on the pump station
  project this month."

This keeps the information relevant and grounded in the worker's
actual work environment — not generic company-wide data (unless the
safety director has enabled cross-project sharing).
```

#### New Response Modes

Replace the five coaching modes (ALERT/VALIDATE/NUDGE/PROBE/AFFIRM) with three:

| Mode | When | Response Pattern |
|------|------|-----------------|
| **ACKNOWLEDGE + REFERENCE** | Uploaded documents contain relevant content | Acknowledge observation → Quote/paraphrase attributed document snippet → Ask one reflective question |
| **ACKNOWLEDGE + REFLECT** | No relevant documents found, or observation is behavioral | Acknowledge observation → Note that no current documents address this → Ask one reflective question → Suggest flagging to supervisor if appropriate |
| **ACKNOWLEDGE + CONNECT** | Worker's trade doesn't match observation, or behavioral pattern worth noting | Acknowledge observation → Connect to worker's trade context or behavioral pattern → Ask how it relates to their work |

All three modes follow the same structure: **acknowledge first, then either reference a document or reflect.** The AI never operates outside this structure.

#### Updated Assessment Output

Keep the `||| JSON` assessment format but update the fields:

```json
{
  "response_mode": "reference|reflect|connect",
  "hazard_category": "string or null",
  "document_referenced": true/false,
  "document_ids": [list of document IDs used, or empty],
  "specificity_score": 1-5,
  "worker_engagement": "high|medium|low",
  "worker_confidence": "confident|uncertain|resistant",
  "teachable_moment": true/false,
  "suggested_next_direction": "deeper|broader|close",
  "trade_match": true/false
}
```

### 2. Coaching Engine (`backend/coaching/engine.py`)

#### `CoachingResult` model (line 36)
Update `response_mode` to accept the new modes: `reference`, `reflect`, `connect` (instead of `alert`, `validate`, `nudge`, `probe`, `affirm`). Add field:
- `document_ids: list[int] = []` — IDs of documents referenced in this response

#### `coach_live()` function (line 400)
Add new parameters:
- `document_context: str = ""` — the formatted document snippets to inject into the system prompt. This gets passed through to `build_system_prompt()`.
- `worker_name: str = ""` — the worker's first name (if collected). Passed through to `build_system_prompt()` for the `NAME_BLOCK`.

The function currently calls `build_system_prompt()` at line 420. Add `document_context` to that call.

Before calling `coach_live()`, the `run_coaching()` function must:
1. Determine the hazard category and trade context (from photo analysis or message keywords)
2. Query the document database for relevant snippets
3. Format the snippets into the `DOCUMENT_CONTEXT_BLOCK`
4. Pass it to `coach_live()` as `document_context`

#### `run_coaching()` function (line 506)
This is the public API. Insert the document retrieval step between session setup and the `coach_live()` / `coach_mock()` call:

```python
# NEW: Retrieve relevant documents before coaching
document_context = ""
document_ids = []
if phone_hash:
    # Determine trade from worker profile or registration
    worker_trade = trade or "general"
    # Query document database (new function — see document layer section)
    from backend.documents.retrieval import retrieve_relevant_documents
    doc_results = retrieve_relevant_documents(
        db=db,
        project_id=worker_project_id,  # from worker registration
        trade=worker_trade,
        observation_text=observation_text,
        media_urls=media_urls,
    )
    document_context = doc_results.formatted_context
    document_ids = doc_results.document_ids
```

After getting the coaching result, log the document references:

```python
# NEW: Log document references
if document_ids:
    from backend.documents.models import DocumentReference
    for doc_id in document_ids:
        ref = DocumentReference(
            phone_hash=phone_hash,
            session_id=session.id if session else None,
            document_id=doc_id,
            observation_id=observation_id,
        )
        db.add(ref)
    db.commit()
```

#### Mock mode (`coach_mock()`, line 323)
Rewrite mock responses to match the new model. Examples:

```python
_MOCK_RESPONSES = {
    "reference": [
        "Got your photo. Your site safety plan covers fall protection for this type of work in Section 3.2. Who else on your crew has seen this area today?",
        "That area shows up in the project safety plan under housekeeping standards. Has this been flagged at a toolbox talk yet?",
    ],
    "reflect": [
        "Got your photo of that area. Nothing in the current site docs covers this specifically — worth bringing up with your foreman. What's your read on it?",
        "Interesting catch. What made you stop and take this photo?",
    ],
    "connect": [
        "Got your photo. That's outside your usual work area — how does this connect to what your crew is doing today?",
        "That's a different setup than what you usually send. What brought you over to this area?",
    ],
}
```

### 3. Worker Profile System (`backend/coaching/profile.py`)

#### Tier Calculation (`calculate_tier()`, line 114)

The current tier calculation weights text length at 10% (`detail level = avg_length / 100`). This punishes low-text workers like Miguel who communicate primarily through photos.

Adjust the weights to better account for photo-first, low-text workers:

**Current weights:**
- Specificity 25%, Engagement 20%, Confidence 15%, Hazard accuracy 15%, Detail level 10%, Initiative 10%, Teaching moments 5%

**New weights:**
- Specificity 20%, Engagement 20%, Confidence 15%, Hazard accuracy 15%, Photo consistency 15%, Initiative 10%, Teaching moments 5%

Replace "detail level" (text length) with "photo consistency" (rate of photo submissions). Workers who consistently send photos are demonstrating engagement even if their text is minimal.

#### Mentor Notes Generation

The `generate_mentor_notes()` function (not shown in the files I read but referenced in profile.py and engine.py) uses Claude to write 3-5 sentence internal notes about the worker. Update the prompt for mentor notes generation to:

- Include which documents have been referenced with this worker
- Note behavioral patterns (is the worker flagging the same issue repeatedly? Are they starting to communicate with coworkers about what they observe?)
- Note cross-session patterns (worker always photographs guardrails — is this their area of concern, or is there a persistent site issue?)
- Do NOT include technical assessments of the worker's safety knowledge

#### New Fields on WorkerProfile

Add to the `WorkerProfile` model in `models.py`:

```python
# Document engagement
document_exposure = Column(Text)  # JSON: {doc_id: {times_referenced, last_referenced}}
```

#### New and Updated Fields on Worker

Add to the `Worker` model in `models.py`:

```python
first_name = Column(String(50), nullable=True)  # Collected during onboarding or consent flow
active_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)  # Current project assignment
project_assigned_at = Column(DateTime, nullable=True)  # When they were assigned to current project
```

The existing `project_id` field on the Worker table stays as the *original* project assignment. The new `active_project_id` represents where the worker is *currently* working. When a safety director moves a worker to a new project (via API or admin interface), `active_project_id` updates and `project_assigned_at` resets. The worker's profile, tier, and behavioral history carry with them — but the document context shifts to the new project's safety plan, hazard register, and observation insights.

The worker's first name is collected during the consent/onboarding flow (when they first text in and complete double opt-in, or when a safety director registers them). It is used by the `NAME_BLOCK` in the prompt to occasionally personalize responses. If not available, the name block is skipped entirely — the system never uses substitutes like "friend" or "buddy."

#### Project Model Enhancement

Add to the `Project` model in `models.py`:

```python
description = Column(Text, nullable=True)  # Brief project description for context injection
                                            # e.g., "Commercial pump station — active excavation,
                                            # underground utilities, concrete foundations"
```

This description is injected into the `PERSONALIZATION_BLOCK` as `{project_context}` so the AI has basic awareness of the project scope. It is written by the safety director, not generated by AI.

### 4. Database Changes (`backend/models.py`)

All changes are additive. No existing tables are modified in breaking ways.

#### New Table: `SafetyDocument`

```python
class SafetyDocument(Base):
    """Uploaded safety document sections — the reference library."""
    __tablename__ = "safety_documents"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)  # null = global/OSHA
    title = Column(String(300), nullable=False)  # Document name
    content = Column(Text, nullable=False)  # Full text of this section/chunk
    category = Column(String(50), nullable=False)  # site_safety_plan, company_procedure, osha_standard, trade_reference, incident_report, lessons_learned, hazard_register, observation_insight
    section_label = Column(String(200))  # Section heading within source document
    trade_tags = Column(Text)  # JSON list of relevant trades
    hazard_tags = Column(Text)  # JSON list of relevant hazard categories
    source_attribution = Column(String(300))  # How to cite this in responses
    language = Column(String(5), default="en")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_safetydoc_project", "project_id"),
        Index("ix_safetydoc_category", "category"),
    )
```

#### New Table: `DocumentReference`

```python
class DocumentReference(Base):
    """Tracks which documents were referenced in which sessions."""
    __tablename__ = "document_references"

    id = Column(Integer, primary_key=True)
    phone_hash = Column(String(64), nullable=False)
    session_id = Column(Integer, ForeignKey("coaching_sessions.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("safety_documents.id"), nullable=False)
    observation_id = Column(Integer, ForeignKey("observations.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ix_docref_phone", "phone_hash"),
        Index("ix_docref_document", "document_id"),
    )
```

#### New Column on `CoachingSession`

```python
document_references_json = Column(Text)  # JSON list of doc IDs used in this session
```

### 5. Document Retrieval System (New Module)

Create `backend/documents/` as a new module:

```
backend/documents/
├── __init__.py
├── retrieval.py     # Query documents by trade, hazard category, keywords
├── ingestion.py     # Upload, chunk, tag documents
└── models.py        # Re-export SafetyDocument, DocumentReference from backend.models
```

#### `retrieval.py` — Core Retrieval Logic

```python
def retrieve_relevant_documents(
    db: Session,
    project_id: int | None,
    trade: str,
    observation_text: str,
    media_urls: list[str] | None = None,
    max_results: int = 3,
) -> DocumentRetrievalResult:
    """Query the document database for relevant safety document sections.

    Strategy (MVP — full-text search, not vector):
    1. Filter by project_id — use the worker's ACTIVE project (active_project_id on Worker model).
       Include project-specific docs (site safety plan, hazard register, observation insights
       for that project) PLUS global docs (OSHA standards, company procedures where project_id
       is null). Project-specific documents are always prioritized over global ones.
    2. Filter by trade_tags (include docs tagged for this trade + docs tagged "all")
    3. Keyword match against observation_text
    4. Prioritize by category — incident_report and lessons_learned are the most
       compelling to workers and should be returned first when available. A real
       incident from the worker's own company is more persuasive than a regulation.
       Suggested priority order:
         a. incident_report / lessons_learned (institutional memory — highest impact)
         b. hazard_register (active known issues on this project)
         c. observation_insight (aggregated observation patterns — social proof, if enabled)
         d. site_safety_plan / company_procedure (project and company requirements)
         e. osha_standard / trade_reference (general industry standards)
    5. Return top N results formatted for prompt injection

    Returns:
        DocumentRetrievalResult with formatted_context string and document_ids list
    """
```

The MVP uses PostgreSQL full-text search or SQLite LIKE queries. Do NOT build vector embeddings or a vector database for the initial implementation. Keep it simple — keyword matching against trade tags and hazard categories is sufficient to prove the concept. Semantic search can be added later without changing the response architecture.

#### `ingestion.py` — Document Upload

```python
def ingest_document(
    db: Session,
    project_id: int | None,
    title: str,
    raw_content: str,
    category: str,
    trade_tags: list[str] | None = None,
    language: str = "en",
) -> list[SafetyDocument]:
    """Upload and chunk a safety document into searchable sections.

    Strategy:
    1. Split document by section headings (##, numbered sections, etc.)
    2. Tag each section with trade relevance and hazard categories
    3. Generate source_attribution string for each section
    4. Store as individual SafetyDocument rows

    Supported categories:
    - site_safety_plan: Project-specific safety requirements from contract docs
    - company_procedure: Company safety rules and standards
    - osha_standard: OSHA/MSHA regulations
    - trade_reference: Trade-specific safety references
    - incident_report: Real incidents from company history (what happened, root cause, lessons)
    - lessons_learned: Post-incident analyses, near-miss summaries, safety bulletins
    - hazard_register: Active hazard observation logs, recurring issues, known problem areas
    - observation_insight: System-generated aggregated observation summaries (not uploaded — auto-generated from observation data by scheduled process, gated by safety director toggle)
    """
```

Also create an API endpoint for document upload. Add to `backend/api/` or extend `backend/api/console.py`:

```python
@router.post("/api/documents/upload")
async def upload_document(
    project_id: int | None = None,
    title: str,
    content: str,  # or file upload
    category: str,
    trade_tags: list[str] | None = None,
):
    """Upload a safety document for the reference library."""
```

### 6. Trades System Update (`backend/coaching/trades.py`)

The 12 trade profiles currently include `coaching_focus` and `osha_focus` fields. Update these to serve the document retrieval layer:

- `osha_focus` becomes a list of OSHA standard references that should be pre-loaded for this trade
- Add `default_hazard_tags` — the hazard categories most relevant to this trade, used to prioritize document retrieval

Example:
```python
"ironworker": {
    "label": "Ironworker",
    "hazard_profile": ["falls from height", "struck-by steel", ...],
    "default_hazard_tags": ["fall_protection", "rigging", "crane_operations", "steel_erection"],
    "osha_references": ["1926.760", "1926.251", "1926.1400"],
    ...
}
```

---

## Hard Rules for the AI (Non-Negotiable)

These rules define what the AI can and cannot do. They are not suggestions. They are the product's liability boundary.

### The AI NEVER:
1. Evaluates whether a setup, rigging plan, or structural condition is safe or unsafe
2. Provides engineering advice, load calculations, or technical specifications
3. Implies it has firsthand trade knowledge or jobsite experience
4. Tells a worker what to do — only asks what they think or who they've talked to
5. Presents information not sourced from uploaded documents
6. Uses first person ("I") in any form — the AI has no self
7. Cites OSHA/MSHA by regulation number unless quoting an uploaded document that contains those citations
8. Says "that looks dangerous," "that's a hazard," "you need to fix that," or any variation that implies a safety judgment
9. Discusses load weights, sling angles, soil types, wind limits, or any engineering parameter from its own knowledge
10. Provides a response that could be interpreted as a work directive

### The AI ALWAYS:
1. Acknowledges what the worker sent before responding
2. Attributes document references to their source ("Your site safety plan says...")
3. Asks one reflective question per response
4. Stays within 25-50 words, under 320 characters
5. Responds in the worker's language (Spanish stays Spanish, always)
6. Ends with a question mark on turns 1-3
7. Makes it personal — references the worker's trade, their patterns, their previous observations
8. Says honestly when no uploaded document covers the observation
9. Suggests the worker talk to their supervisor or coworkers when appropriate
10. Invites a reply — no dead-end responses

---

## Example Interactions (Target State)

### Example 1: Carpenter sends photo of scaffold without guardrail
**Worker:** *(photo)* no tiene barandal
**System retrieves:** Site Safety Plan, Section 3.4 — Fall Protection Requirements
**Response:** "Got your photo. The site safety plan requires guardrails above 6 feet on all scaffolds (Section 3.4). Have you flagged this to your foreman?"
**Mode:** ACKNOWLEDGE + REFERENCE

### Example 2: Carpenter sends photo of excavation (trade mismatch)
**Worker:** *(photo)* mira
**System retrieves:** No carpentry-relevant documents for excavation context
**Response:** "Got your photo of that excavation. How does this connect to the framing work you're doing nearby — anything about the layout that affects your crew's access?"
**Mode:** ACKNOWLEDGE + CONNECT

### Example 3: Ironworker sends photo of rigging setup (with name)
**Worker (Jake):** *(photo)* Setting up for a pick. Want a second set of eyes.
**System retrieves:** Company Rigging Procedure, Section 2.1 — Pre-Lift Checklist
**Response:** "Busy setup for that pick, Jake. The company rigging procedure has a pre-lift checklist in Section 2.1. Have you walked through it with your signal person yet?"
**Mode:** ACKNOWLEDGE + REFERENCE
**Note:** Name used here because it's been 3+ responses since last name usage. Dropped naturally into the acknowledgment.

### Example 4: Worker sends photo, no relevant documents exist
**Worker:** *(photo)* esto
**System retrieves:** Nothing relevant found
**Response:** "Got your photo — lot going on over there. Nothing in the current site docs covers this specifically. What caught your eye about this area?"
**Mode:** ACKNOWLEDGE + REFLECT

### Example 5: Worker takes action (behavioral reinforcement)
**Worker:** puse cinta amarilla
**Response:** "Good move taping that off. Did you let the rest of the crew know that area's closed?"
**Mode:** ACKNOWLEDGE + REFLECT

### Example 6: Repeat pattern across sessions (personalization)
**Worker:** *(photo)* andamio sin barandal *(third time flagging this)*
**Response:** "Third time you've flagged guardrails — that's a pattern worth bringing up at the next toolbox talk. The site safety plan covers it in Section 3.4. Have you talked to your foreman about making this a standing item?"
**Mode:** ACKNOWLEDGE + REFERENCE + CONNECT (behavioral pattern)

### Example 7: Incident report surfaces from company knowledge base
**Worker:** *(photo of a grinder sitting on a work table)*
**System retrieves:** Incident Report #2014-037 — Hand laceration from unguarded angle grinder
**Response:** "Got your photo. The company had an incident back in 2014 where someone was cut using a grinder without a guard (Incident #2014-037). Has anyone on your crew gone over that one?"
**Mode:** ACKNOWLEDGE + REFERENCE (incident history)

### Example 8: Lessons learned from near-miss log
**Worker:** *(photo of materials stacked near an edge)*
**System retrieves:** Near-Miss Report NM-2025-12 — Materials shifted off elevated deck during wind event
**Response:** "That stack is close to the edge. There's a near-miss from last year where materials shifted off a deck in wind (NM-2025-12). What's the weather looking like this afternoon?"
**Mode:** ACKNOWLEDGE + REFERENCE (lessons learned)

### Example 9: Hazard register match
**Worker:** *(photo of a walkway with cables across it)*
**System retrieves:** Project Hazard Register entry — "Temporary power routing across pedestrian paths, Building C east corridor" (open item, logged 3/12/2026)
**Response:** "That cable routing is already on the project hazard register from two weeks ago. Has anyone followed up on rerouting it, or is it still the same setup?"
**Mode:** ACKNOWLEDGE + REFERENCE (hazard register)

### Example 10: Social feedback — observation pattern across company (with name)
**Worker (Miguel):** *(photo of open trench without shoring)*
**System retrieves:** Observation Insight Report (auto-generated, March 2026) — "7 unshored trench observations across 3 projects this month"
**Response:** "Miguel, buena observación. No eres el único que está viendo esto — han habido siete observaciones similares en la empresa este mes. ¿Ya lo hablaste con tu supervisor?"
**Mode:** ACKNOWLEDGE + REFERENCE (social/aggregate)

### Example 11: Social feedback — worker sees their impact (project-specific)
**Worker (on the Riverton Pump Station project):** *(photo of properly barricaded area)*
**System retrieves:** Observation trend data — "Fall protection observations on Riverton Pump Station up 40% this quarter"
**Response:** "Clean barricade setup. Fall protection observations on Riverton are up 40% this quarter — your crew is driving that. Anything else jumping out today?"
**Mode:** ACKNOWLEDGE + CONNECT (social proof / engagement)
**Note:** Project name referenced naturally. The system knows the worker is assigned to Riverton Pump Station and scopes the insight accordingly.

---

## Social Feedback Loop

This section describes how worker observations flow back into the document layer as aggregated insight, creating a feedback loop that drives engagement and gives workers visibility into the collective impact of reporting.

### The Problem This Solves

The biggest adoption killer in safety reporting tools is the feeling that you're shouting into a void. A worker sends a photo, gets a response, and then nothing. They have no idea if anyone else is dealing with the same conditions. They have no visibility into whether their reporting had any impact. Engagement drops because there's no social proof that the tool is alive and useful.

### How It Works

1. **Observations accumulate** — Every worker interaction creates an observation record in the database (this already exists). Each observation is tagged with hazard category, trade context, project, and severity.

2. **The system generates periodic insight reports** — A scheduled process (daily, weekly, or monthly — configurable by the safety director) aggregates observation data into insight summaries. These are NOT AI-generated opinions. They are statistical summaries of real observation data. Insights are generated at two scopes:

   **Project-level insights** (always generated, scoped to the worker's active project):
   - "10 housekeeping observations on the Riverton Pump Station project this month"
   - "3 workers on Riverton flagged the same trench condition in the last 10 days"
   - "Fall protection observations on Riverton are up 40% this quarter"

   **Company-level insights** (only shared if the safety director enables cross-project sharing):
   - "12 fall protection observations across 4 projects this month"
   - "Your project has the highest observation engagement rate in the company this week"
   - "Seven similar trench observations across three job sites"

3. **Insight reports are published into the document layer** — These summaries become searchable documents in the `safety_documents` table with `category = 'observation_insight'`. They are tagged with the relevant trades, hazard categories, and project IDs so the retrieval system can match them to incoming observations.

4. **The safety director controls what gets shared** — This is gated by a toggle. Not all aggregated data should be visible to all workers. The safety director decides:
   - Whether observation insights are shared back to workers at all
   - Whether cross-project data is visible (company-wide trends) or only same-project data
   - What level of detail is shared (just counts and trends, or more specific summaries)
   - This is a dashboard setting, not a prompt engineering problem

5. **Workers see their collective impact** — When a worker sends a photo and the system finds a matching insight report, it surfaces the aggregate data. The worker learns they're part of something bigger. This reinforces reporting behavior through social proof.

### Why This Is Safe (Liability-wise)

The social feedback layer does not generate safety advice. It surfaces statistical facts about observation data that real workers submitted. "Seven other workers flagged similar conditions this month" is a factual statement about the database, not an engineering judgment. The AI is reporting what the data shows, not interpreting what it means.

### Implementation Notes

This is a Phase 5 feature — it depends on Phases 1-4 being complete and real observation data accumulating. For the MVP, the insight generation can be simple: SQL queries that count observations by hazard category, project, and time period, formatted into short text summaries and inserted into the `safety_documents` table.

The scheduled generation process should be a standalone script or management command:
```
# Generate insights for a specific project
python -m backend.documents.generate_insights --period weekly --project-id 1

# Generate company-wide insights across all projects
python -m backend.documents.generate_insights --period monthly --company-id 1 --scope company
```

The database schema already supports this — `safety_documents` with `category = 'observation_insight'` and `project_id` set appropriately. No new tables required.

### New Document Category

Add to the supported categories:
- `observation_insight` — System-generated aggregated observation summaries. Auto-generated by scheduled process. Gated by safety director toggle. Contains statistical facts about observation patterns, not AI-generated opinions.

---

## Implementation Phases

### Phase 1: Prompt Architecture Rebuild
**Files:** `backend/coaching/prompts.py`
**Scope:** Rewrite the system prompt blocks. Remove trade-expert identity. Add document context injection. Add reflection and personalization blocks. Update response rules and modes. Update assessment output format.
**Test:** Can run existing evaluation pipeline against new prompt (even without real documents) to verify the AI no longer generates technical advice.

### Phase 2: Document Layer
**Files:** `backend/models.py`, `backend/documents/` (new module), `backend/api/`
**Scope:** Create database tables. Build ingestion and retrieval functions. Create upload API endpoint. Seed with sample OSHA standards and a test site safety plan.
**Test:** Can upload a document, query it by trade and hazard category, get formatted snippets back.

### Phase 3: Engine Integration
**Files:** `backend/coaching/engine.py`, `backend/coaching/profile.py`
**Scope:** Wire document retrieval into the coaching pipeline. Update `run_coaching()` to query documents before building prompt. Update `CoachingResult` model. Update mock mode. Update worker profile with document exposure tracking. Adjust tier calculation weights.
**Test:** Full end-to-end flow — worker sends message, system retrieves documents, generates document-grounded response, logs references, updates profile.

### Phase 4: Evaluation Framework Update
**Files:** `training/evaluators/*.py`, `training/quality_gate.py`
**Scope:** Retool quality gate scoring for new criteria. New evaluation categories: document accuracy (did the response correctly reference uploaded docs?), attribution correctness (is the source cited?), reflection quality (is the question reflective, not technical?), absence of technical advice (does the response contain any engineering judgments?), trade-aware personalization (did the response acknowledge the worker's trade context?).
**Test:** Run full evaluation with Miguel and Jake personas against new prompt. Compare against v1.1 baseline.

### Phase 5: Social Feedback Loop
**Files:** `backend/documents/insights.py` (new), scheduled task or management command
**Scope:** Build the observation aggregation engine. Create scheduled process that generates insight summaries from observation data and publishes them into the document layer as `observation_insight` documents. Add safety director toggle (project-level setting) that controls whether insights are shared back to workers and at what scope (same-project only vs. company-wide). Update document retrieval to include `observation_insight` category.
**Depends on:** Phases 1-4 complete and real observation data accumulating. Can be simulated with synthetic data for testing.
**Test:** Generate insight reports from test observation data. Verify they surface correctly when a worker sends a matching observation.

---

## Files Quick Reference

| File | What Changes |
|------|-------------|
| `backend/coaching/prompts.py` | Major rewrite — new identity, modes, blocks |
| `backend/coaching/engine.py` | Add document retrieval step, update result model, rewrite mock responses |
| `backend/coaching/profile.py` | Adjust tier weights, update mentor notes prompt, add document exposure |
| `backend/coaching/trades.py` | Add default_hazard_tags and osha_references per trade |
| `backend/models.py` | Add SafetyDocument, DocumentReference tables; add document_exposure to WorkerProfile |
| `backend/documents/__init__.py` | New module |
| `backend/documents/retrieval.py` | New — document query logic |
| `backend/documents/ingestion.py` | New — document upload and chunking |
| `backend/api/console.py` or new file | New endpoint for document upload |
| `training/evaluators/*.py` | Retool scoring rubrics |
| `training/quality_gate.py` | Update pass/fail criteria |
| `CLAUDE.md` | Update project description to reflect pivot |
| `docs/PRODUCT_VISION.md` | Update to reflect new model |
| `docs/BEHAVIORAL_FRAMEWORK.md` | May need updates |

---

## Critical Context from Testing

The `training_reports/` folder contains four files documenting the current state:

- `BASELINE_REPORT.md` — v1.0 evaluation results (March 17, 2026). Neither persona passed the quality gate.
- `PROMPT_TUNING_SPRINT_REPORT.md` — v1.0 → v1.1 comparison (March 23, 2026). Significant improvements in question ratio, behavioral science, and authenticity. Longitudinal coherence still fails for both personas.
- `TRANSCRIPT_JAKE.md` — Full 15-session transcript for Jake (ironworker). Shows what the coaching does well (trade credibility, psychological safety) and what it does wrong (technical advisory drift, longitudinal plateau).
- `TRANSCRIPT_MIGUEL.md` — Full 15-session transcript for Miguel (laborer, Spanish). Shows the system's failure with low-engagement, photo-first, Spanish-speaking workers.

Key findings that drive this pivot:
1. The AI sounds too knowledgeable — 4.80/5.0 trade credibility is a liability, not an asset
2. The coaching drifts toward advisory (discussing sling angles, bearing surfaces, soil stability)
3. Miguel never progressed a single tier because the algorithm punishes low-text workers
4. Session 11 (Miguel) was 4 turns of "send me a photo" with zero coaching — the system had no fallback for text-only sessions
5. The AI grading AI problem — the entire evaluation pipeline is synthetic. Real validation requires real workers.

The evaluation infrastructure (7-agent system, ~$2-3 per run, ~500 API calls per version) is valuable for iteration but should not be treated as ground truth for whether the product works with real humans.
