# White-Label Safety Document Library — Product Brief

**Status:** Future feature — documented for reference, not currently in development
**Last updated:** March 2026
**Author:** Travis Sparks + Claude (product strategy session)

---

## The Problem

Safety as a Contact is a document-grounded system. The AI only surfaces content from uploaded documents — it never generates technical safety advice from its own training data. This is the core architectural decision that eliminates liability.

But this creates a cold-start problem: **if a company doesn't have a mature safety program, the document layer is empty.** A 75-person concrete subcontractor who signs up without a written fall protection program, a housekeeping standard, or documented incident history gets a system that can only ask reflective questions. They miss the entire document-reference layer — the part of the product that makes real policies and procedures feel immediate and relevant to what a worker is doing right now.

The target market makes this worse, not better. We're not building for Kiewit or Granite. We're building for companies in the 50-250 employee range — the ones most likely to have gaps in their written safety programs, and the ones who would benefit most from having one.

## The Solution

A **white-label safety document library** — a curated set of OSHA-compliant (and where applicable, MSHA-compliant) policies, procedures, and reference documents that ship with the platform as a default content layer. These documents are pre-tagged by trade, hazard category, and document type, and they slot directly into the existing `SafetyDocument` table with `project_id = None` (global scope).

When a company signs up:
- Day one, before the safety director uploads anything, the system already has baseline content
- Workers text photos and get real document references with attribution
- The attribution is honest: "OSHA-Based Fall Protection Program" or "Industry Standard: Scaffold Safety" — never "Your Company's Policy"
- As the company uploads their own documents, those take retrieval priority over the white-label defaults
- The white-label content remains as a fallback for topics the company hasn't covered yet

## Business Value

**For the customer:**
- Immediate value on day one — no setup required to start getting useful responses
- A starting point for building their own safety program — they can see what a complete program looks like through the documents the AI references, then write their own versions
- Covers regulatory compliance basics even if they haven't formalized their own procedures

**For us:**
- Removes the biggest adoption barrier (empty document library = weak product experience)
- Creates a natural upgrade path: white-label defaults → customized company documents → mature safety program
- Positions Safety as a Contact as both a mentorship tool AND a safety program development pathway
- Differentiator for the 50-250 employee market where safety program maturity is lowest

## Architecture Fit

This requires **zero code changes** for the basic version. The existing system already supports it:

1. **`SafetyDocument` table** — already has `project_id` nullable. White-label docs have `project_id = None` (global scope).
2. **Retrieval priority** — `retrieve_relevant_documents()` already filters by `project_id` first (project-specific), then falls through to global docs. Company-uploaded documents automatically take priority.
3. **Trade tags and hazard tags** — already supported. White-label docs get tagged the same way any uploaded document would.
4. **Attribution** — `source_attribution` field already exists. White-label docs get attributions like "OSHA-Based Fall Protection Program (Industry Standard)" to distinguish them from company-specific content.

The only new work is:
- Writing the actual document content
- A seed script that ingests the white-label library on platform setup
- A company-level flag indicating whether to include white-label content in retrieval (opt-out, not opt-in — defaults to on)
- Admin UI to let safety directors see which white-label docs are active and which have been superseded by company uploads

## Document Library Scope

### Regulatory Framework Tags

Each document should be tagged with its regulatory framework:
- **OSHA** — general industry and construction (29 CFR 1926)
- **MSHA** — mining operations (30 CFR Parts 46, 48, 56, 57, 62, 70, 71, 72, 75, 77)

A company-level setting (construction vs. mining) filters which regulatory framework applies. A concrete contractor should never see mining regulations.

### Minimum Viable Library (OSHA Construction)

Target: 15-20 documents covering the most common construction hazards and procedures. Each written in plain, practical language — not regulatory legalese. Chunked by section with trade tags and hazard tags, exactly like any uploaded document.

**OSHA Focus Four (highest priority — these account for most construction fatalities):**

1. Fall Protection Program (1926.501/502)
   - When fall protection is required (6-foot rule)
   - Types of fall protection systems (guardrails, nets, personal fall arrest)
   - Inspection requirements for harnesses, lanyards, anchors
   - Leading edge and hole protection
   - Trade tags: all

2. Struck-By Prevention (1926.250, .251, .550-.556)
   - Falling object protection
   - Vehicle and equipment struck-by
   - Crane operations and rigging safety
   - Exclusion zones and barricades
   - Trade tags: all, ironworker, operator

3. Caught-In/Between Prevention (1926.650-.652)
   - Excavation and trenching protective systems
   - Sloping, shoring, and shielding
   - Competent person requirements
   - Soil classification
   - Trade tags: all, operator, laborer

4. Electrocution Prevention (1926.404-.408)
   - GFCI protection for temporary power
   - Lockout/tagout procedures
   - Power line clearance distances
   - Qualified vs. unqualified workers
   - Trade tags: all, electrician

**Common Construction Standards:**

5. Scaffolding Safety (1926.451-.454)
   - Erection and dismantling by competent person
   - Capacity and loading requirements
   - Access requirements
   - Inspection protocols
   - Trade tags: all, carpenter, laborer

6. Ladder Safety (1926.1053)
   - Three-point contact
   - Setup angles and securing
   - Inspection and defective equipment
   - Trade tags: all

7. PPE Requirements (1926.95-.107)
   - Head, eye, face, hand, foot protection
   - When each type is required
   - Inspection and replacement
   - Trade tags: all

8. Housekeeping Standards (1926.25)
   - Work area cleanliness
   - Material storage and stacking
   - Waste disposal
   - Walkway and access maintenance
   - Trade tags: all

9. Hot Work / Fire Prevention (1926.150-.159, .350-.354)
   - Hot work permits
   - Fire watch requirements
   - Fire extinguisher placement and types
   - Flammable material storage
   - Trade tags: all, ironworker, pipefitter, welder

10. Confined Space Entry (1926.1200-.1213)
    - Permit-required vs. non-permit spaces
    - Atmospheric testing
    - Rescue planning
    - Attendant and entrant duties
    - Trade tags: all, pipefitter, electrician

11. Crane and Rigging Safety (1926.1400-.1442)
    - Qualified rigger requirements
    - Lift planning
    - Signal person duties
    - Inspection protocols
    - Trade tags: ironworker, operator

12. Concrete and Masonry (1926.700-.706)
    - Formwork and shoring
    - Post-tensioning safety
    - Concrete pump operations
    - Trade tags: carpenter, laborer, operator

13. Steel Erection (1926.750-.761)
    - Connector fall protection
    - Column stability and anchor bolts
    - Controlled decking zone
    - Trade tags: ironworker

14. Hazard Communication (1926.59, GHS)
    - SDS availability and reading
    - Chemical labeling
    - Exposure limits
    - Trade tags: all

15. Heat Illness Prevention (no specific OSHA standard — general duty clause + guidance)
    - Water, rest, shade
    - Acclimatization protocols for new workers
    - Signs and symptoms recognition
    - Buddy system procedures
    - Trade tags: all

**Additional documents as needed:**

16. Silica Exposure (1926.1153) — Trade tags: all, carpenter, laborer
17. Noise and Hearing Conservation (1926.52, .101) — Trade tags: all
18. Stairways (1926.1052) — Trade tags: all
19. Hand and Power Tools (1926.300-.307) — Trade tags: all, carpenter
20. Welding and Cutting (1926.350-.354) — Trade tags: ironworker, pipefitter, welder

### MSHA Library (future — separate effort)

Not scoped here. Mining operations have fundamentally different hazard profiles, regulatory structures, and terminology. The MSHA white-label library would be a separate content project with its own document set, tagged under the MSHA regulatory framework.

## Attribution Rules

When the AI references a white-label document, the attribution must be clearly distinguished from company-specific content:

- **White-label:** "OSHA-Based Fall Protection Program (Industry Standard), Section: Harness Inspection"
- **Company-specific:** "Acme Construction Fall Protection Plan (Site Safety Plan), Section 3.2"

The worker should always be able to tell whether they're reading from their company's own document or from a general industry standard. This is both an honesty principle and a liability consideration.

## Override Behavior

When a company uploads their own document that covers a topic already in the white-label library:

1. The company document takes retrieval priority (already handled by project-scoped filtering)
2. The white-label document remains available as fallback for gaps
3. No manual deactivation needed — the retrieval layer handles priority automatically
4. The admin dashboard should show which white-label topics have been "covered" by company uploads

Example: Company uploads their own fall protection plan. For fall protection queries, the company plan surfaces first. But if a worker asks about confined space entry and the company hasn't uploaded a confined space procedure, the white-label version still surfaces.

## Implementation Approach (when ready)

**Phase 1 — Content Development:**
- Write the 15-20 core OSHA documents in plain language
- Each document structured with markdown headings (## sections) so the existing ingestion system chunks them correctly
- Trade tags and hazard tags assigned per document
- Attribution strings follow the white-label format
- Estimated effort: 2-3 days of content writing

**Phase 2 — Seed Script:**
- Python script that ingests all white-label documents into the database
- Runs on platform setup or when a new company is onboarded
- Idempotent — can be re-run without creating duplicates
- Estimated effort: half day

**Phase 3 — Company Controls:**
- Company-level setting: `use_white_label_library` (boolean, default True)
- Admin dashboard view showing white-label document coverage
- Indicator showing which topics have been superseded by company uploads
- Estimated effort: 1-2 days

**Phase 4 — MSHA expansion (separate project):**
- Scoped and estimated separately when there's market demand

## Open Questions

1. **Versioning:** When OSHA updates a standard, do we version the white-label documents or replace them? Likely replace with a changelog, but needs thought.
2. **Customization:** Should companies be able to fork a white-label document and edit it as their own? Could accelerate safety program development but adds complexity.
3. **Language:** Should we create Spanish-language versions of the white-label documents, or rely on the Spanish→English keyword expansion in the retrieval layer? Given the target market, English-only documents with the existing keyword translation is probably sufficient for MVP.
4. **Pricing:** Is the white-label library included in the base product, or is it a separate tier? Strong argument for including it — it solves the cold-start problem that would otherwise hurt adoption.

---

*This document captures a product concept discussed during the pivot validation phase. It is not currently in development. The existing architecture supports this feature with minimal code changes — the primary work is content development.*
