"""Live API validation — tests actual Claude Haiku responses against pivot behavioral rules.

Seeds an in-memory database with workers + safety documents, then runs 10 observation
scenarios through the live Claude API and evaluates every response against the pivot's
hard rules and soft criteria.

Run:     python -m tests.live_validation
Requires: ANTHROPIC_API_KEY environment variable
"""

import os
import sys
from pathlib import Path

# ── Pre-flight: load .env if API key not already in environment ──────────
if not os.environ.get("ANTHROPIC_API_KEY"):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("\"'")
                if key and value:
                    os.environ.setdefault(key, value)

if not os.environ.get("ANTHROPIC_API_KEY"):
    print()
    print("  ERROR: ANTHROPIC_API_KEY environment variable is required.")
    print("  Set it:  export ANTHROPIC_API_KEY=sk-ant-...")
    print("  Or add it to project .env file.")
    print()
    sys.exit(1)

import json
import time
from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import (
    Company,
    Project,
    Worker,
    Observation,
    hash_phone,
    utcnow,
)
from backend.documents.ingestion import ingest_document
from backend.documents.retrieval import retrieve_relevant_documents
from backend.coaching.engine import coach_live
from backend.coaching.trades import get_trade_profile


# ── Prohibited phrases (comprehensive — prompts.py + test suite) ─────────

PROHIBITED_PHRASES = [
    "that setup looks unsafe",
    "that looks unsafe",
    "that's a hazard",
    "that is a hazard",
    "that needs to be fixed",
    "you need to",
    "you should",
    "make sure you",
    "i can see that",
    "i notice that",
    "it looks like",
    "i recommend",
    "i suggest",
    "i advise",
    "based on my experience",
    "in my experience",
    "from what i can see",
    "that's not right",
    "that's incorrect",
    "that's wrong",
    "that's dangerous",
    "that is dangerous",
    "that's a violation",
    "you're doing it wrong",
    "you need to fix",
    "you should fix",
    "you must",
    "you have to",
    "don't do that",
    "stop doing that",
    "that won't work",
    "that's not going to work",
    "here's what you should do",
    "let me tell you",
    "i think you should",
    "the correct way",
    "the right way",
    "the proper way",
    "i can tell",
    "i can see",
    "i see that",
    "looking at this",
    "what i see here",
    "i'm seeing",
    "it appears that",
    "clearly",
    "obviously",
    "you failed to",
    "you forgot to",
    "you missed",
    "you overlooked",
    "be careful",
    "osha requires",
    "safety first",
    "great job!",
    "remember to",
    "important to note",
    "best practice",
    "ensure that",
    "i noticed that",
    "based on the image",
    "your safety score",
    "your progress",
    "assessment",
    "what're",
    "how're",
    "where're",
    "i can",
    "i see",
    "i notice",
    "i think",
    "i would",
    "i'd ",
    "i'll",
    "i'm",
    "i've",
    "so i ",
    "let me",
]


TECHNICAL_PATTERNS = [
    "make sure the",
    "ensure the",
    "check the",
    "verify that",
    "always use",
    "never use",
    "you need a",
    "you'll want to",
    "the correct procedure is",
    "the sling angle should",
    "the bearing surface",
    "the load capacity",
    "rated for",
    "the minimum distance",
]


FIRST_PERSON_PATTERNS = [
    "i can",
    "i see",
    "i can see",
    "i notice",
    "i think",
    "i recommend",
    "i suggest",
    "i advise",
    "i'm seeing",
    "i can tell",
    "i would",
    "i'd ",
    "i'll",
    "i'm",
    "i've",
    "so i ",
    "let me",
    "in my",
]


# ── Scenarios ────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": 1,
        "worker": "jake",
        "text": "No guardrails on the east side of floor 9, crew still working the edge",
        "has_photo": True,
    },
    {
        "id": 2,
        "worker": "jake",
        "text": "Bolt on the ground near the connection area, looks like it fell from above",
        "has_photo": True,
    },
    {
        "id": 3,
        "worker": "jake",
        "text": "Crane picking a load and I don't see tag lines on it",
        "has_photo": True,
    },
    {
        "id": 4,
        "worker": "miguel",
        "text": "Mira, hay rebar expuesto aqui cerca del andamio",
        "has_photo": True,
    },
    {
        "id": 5,
        "worker": "miguel",
        "text": "Estamos cortando madera pero la sierra no tiene guarda",
        "has_photo": True,
    },
    {
        "id": 6,
        "worker": "miguel",
        "text": "\U0001f4f7",  # camera emoji — photo only, no text
        "has_photo": True,
    },
    {
        "id": 7,
        "worker": "sarah",
        "text": "Open electrical panel on level 7, nobody working on it but it's not locked out",
        "has_photo": True,
    },
    {
        "id": 8,
        "worker": "sarah",
        "text": "Saw a new guy carrying material in the heat, he's been out there all morning",
        "has_photo": True,
    },
    {
        "id": 9,
        "worker": "sarah",
        "text": "Housekeeping on level 12 is really good today, crew did a great job",
        "has_photo": True,
    },
    {
        "id": 10,
        "worker": "jake",
        "text": "Everything looks good out here today",
        "has_photo": False,
    },
]


# ── Database setup ───────────────────────────────────────────────────────

def setup_database():
    """Create in-memory SQLite database, seed company/project/workers/documents."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = SessionLocal()

    # ── Company + Project ──
    company = Company(name="Wollam Construction")
    db.add(company)
    db.commit()
    db.refresh(company)

    project = Project(
        company_id=company.id,
        name="Downtown Office Tower",
        location="1200 Main St, Dallas TX",
        description=(
            "14-story steel frame office building. Active floors 6-14. "
            "Crane operations daily. Concrete pours on 3-day cycle."
        ),
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # ── Workers ──
    jake = Worker(
        phone_hash=hash_phone("+15551001001"),
        company_id=company.id,
        project_id=project.id,
        active_project_id=project.id,
        first_name="Jake",
        trade="ironworker",
        experience_level="intermediate",
        preferred_language="en",
    )
    miguel = Worker(
        phone_hash=hash_phone("+15551002002"),
        company_id=company.id,
        project_id=project.id,
        active_project_id=project.id,
        first_name="Miguel",
        trade="carpenter",
        experience_level="entry",
        preferred_language="es",
    )
    sarah = Worker(
        phone_hash=hash_phone("+15551003003"),
        company_id=company.id,
        project_id=project.id,
        active_project_id=project.id,
        first_name="Sarah",
        trade="electrician",
        experience_level="expert",
        preferred_language="en",
    )
    db.add_all([jake, miguel, sarah])
    db.commit()
    for w in [jake, miguel, sarah]:
        db.refresh(w)

    # ── Seed documents (copied from test_pivot_integration.py) ──

    # 1. Site Safety Plan (project-specific)
    ingest_document(
        db,
        project_id=project.id,
        title="Downtown Office Tower Site Safety Plan",
        raw_content="""## Fall Protection Requirements
All workers operating at heights above 6 feet must use personal fall arrest systems.
Guardrails are required on all open sides of floors, platforms, and walkways.
Leading edge work requires a written fall protection plan reviewed by the site safety director.
Workers must inspect harness and lanyard connections before each use.

## Housekeeping Standards
All work areas must be cleaned at end of each shift. Debris must not accumulate near
floor edges or stairwells. Material staging areas must be clearly marked with barriers.
Combustible waste must be placed in designated containers and removed daily.

## Crane Operations
Only qualified riggers may attach loads. All crane picks must have a lift plan.
Tag lines required on all loads. No workers under suspended loads at any time.
Signal person must have unobstructed view of load and operator.

## Electrical Safety
All temporary power must be GFCI protected. Lockout/tagout procedures required
before any electrical work. Minimum 10-foot clearance from overhead power lines.
Only qualified electricians may work on energized circuits.

## Excavation and Trenching
All excavations deeper than 5 feet require protective systems (sloping, shoring, or shield).
Competent person must inspect excavations daily and after rain events.
Spoil piles must be at least 2 feet from trench edge.""",
        category="site_safety_plan",
        trade_tags=["all"],
        hazard_tags=["fall_protection", "housekeeping", "crane", "electrical", "excavation"],
    )

    # 2. Incident Report (company-wide)
    ingest_document(
        db,
        project_id=None,
        title="Incident Report #2024-017: Near-Miss Falling Object",
        raw_content="""## Incident Summary
On March 12, 2024, a 3/4-inch bolt fell from the 9th floor during steel erection,
landing 4 feet from a carpenter working on the 6th floor deck. No injuries occurred.
The bolt had not been secured in the connector bolt bag after installation.

## Root Cause
Ironworker did not follow the bolting procedure which requires all loose connectors
to be stored in the bolt bag between installations. The bolt bag was not attached
to the worker's harness as required by company procedure.

## Corrective Actions
1. All ironworkers retrained on connector bolt storage procedure.
2. Bolt bags now inspected during daily harness checks.
3. Exclusion zone below active steel erection expanded from 15 to 25 feet.
4. Nets installed below active connection points on floors 7 through 14.""",
        category="incident_report",
        trade_tags=["ironworker", "carpenter", "all"],
        hazard_tags=["falling_object", "struck_by"],
    )

    # 3. OSHA Standard reference (global)
    ingest_document(
        db,
        project_id=None,
        title="OSHA 1926.501 - Fall Protection Scope and Requirements",
        raw_content="""## General Requirements
Each employee on a walking/working surface with an unprotected side or edge
which is 6 feet or more above a lower level shall be protected from falling by
the use of guardrail systems, safety net systems, or personal fall arrest systems.

## Leading Edge Work
Each employee who is constructing a leading edge 6 feet or more above lower levels
shall be protected from falling by guardrail systems, safety net systems, or
personal fall arrest systems.

## Hoist Areas
Each employee in a hoist area shall be protected from falling 6 feet or more to
lower levels by guardrail systems or personal fall arrest systems.""",
        category="osha_standard",
        trade_tags=["all"],
        hazard_tags=["fall_protection"],
    )

    # 4. Trade Reference — Carpentry (trade-specific)
    ingest_document(
        db,
        project_id=project.id,
        title="Carpentry Safe Work Practices - Formwork",
        raw_content="""## Formwork Erection Safety
All formwork must be designed by a qualified person. Shoring must be inspected
before concrete placement. Workers must verify shore loads do not exceed
manufacturer ratings. Reshoring required on multi-story pours.

## Saw Operations
All portable circular saws must have functioning guards. Push sticks required
for table saw operations. Workers must wear eye protection and hearing protection
when operating saws. Ensure blade is appropriate for material being cut.

## Material Handling
Lumber and plywood must be stacked on level surfaces with proper dunnage.
Stack height must not exceed 16 feet. Band materials before hoisting.
Workers must use proper lifting techniques — get help for loads over 50 lbs.""",
        category="trade_reference",
        trade_tags=["carpenter"],
        hazard_tags=["formwork", "saw_operations", "material_handling"],
    )

    # 5. Lessons Learned (company-wide)
    ingest_document(
        db,
        project_id=None,
        title="Lessons Learned: Heat Illness Prevention Summer 2024",
        raw_content="""## Summary
During summer 2024, we had 3 heat-related incidents across company projects.
Two were heat exhaustion cases on concrete pour days, one was heat stroke
requiring emergency medical response.

## Key Findings
Workers on concrete pour days are at highest risk due to extended sun exposure
and physical exertion. Hydration stations more than 100 feet from work areas
were underutilized. New workers (less than 2 weeks on site) accounted for
all 3 incidents.

## Recommendations
Hydration stations within 50 feet of active work areas. Mandatory buddy system
on days above 95F. Acclimatization protocol for all new workers: reduced
workload first 2 weeks. Foremen trained to recognize early signs.""",
        category="lessons_learned",
        trade_tags=["all"],
        hazard_tags=["heat_illness", "environmental"],
    )

    workers = {"jake": jake, "miguel": miguel, "sarah": sarah}
    return db, workers, project


# ── Evaluation helpers ───────────────────────────────────────────────────

def check_prohibited_phrases(text: str) -> list[str]:
    """Return any prohibited phrases found in the response text."""
    lower = text.lower()
    return [p for p in PROHIBITED_PHRASES if p in lower]


def check_technical_advice(text: str) -> list[str]:
    """Return any technical advice patterns found in the response text."""
    lower = text.lower()
    return [p for p in TECHNICAL_PATTERNS if p in lower]


def check_first_person(text: str) -> list[str]:
    """Return any first-person constructions found in the response text."""
    lower = text.lower()
    return [p for p in FIRST_PERSON_PATTERNS if p.strip() in lower]


def detect_language(text: str) -> str:
    """Detect whether response text is primarily Spanish or English."""
    words = text.lower().split()
    cleaned = [w.strip(".,!?¿¡()\"':-") for w in words]

    spanish = {
        "el", "la", "los", "las", "un", "una", "del", "con", "por", "para",
        "que", "tu", "su", "esta", "está", "es", "hay", "como", "ya", "pero",
        "más", "también", "sobre", "ese", "esa", "eso", "esto", "aquí", "ahí",
        "donde", "cuando", "porque", "buena", "bueno", "foto", "área", "zona",
        "equipo", "seguridad", "trabajo", "sitio", "plan", "sección", "algo",
        "esa", "ese", "eso", "tus", "nos", "ese", "esas", "esos", "algo",
        "alguien", "nadie", "nada", "mucho", "poco", "otro", "otra",
    }
    english = {
        "the", "is", "are", "your", "you", "this", "that", "what", "how",
        "has", "have", "been", "was", "it", "for", "with", "from", "they",
        "who", "does", "got", "here", "there", "would", "about", "crew",
        "area", "photo", "plan", "site", "safety", "section",
    }

    es_count = sum(1 for w in cleaned if w in spanish)
    en_count = sum(1 for w in cleaned if w in english)

    return "es" if es_count > en_count else "en"


def check_document_attribution(
    text: str, doc_ids: list[int], lang: str, response_mode: str = "",
) -> bool:
    """Check if response contains document attribution when docs were retrieved.

    Returns True if:
    - No docs were retrieved (nothing to attribute)
    - Response mode is reflect/connect (AI chose not to reference docs — valid)
    - Attribution markers are present in text
    """
    if not doc_ids:
        return True  # Nothing to attribute
    if response_mode in ("reflect", "connect"):
        return True  # AI intentionally chose not to reference — valid behavior

    lower = text.lower()

    markers_en = [
        "safety plan", "site plan", "plan covers", "plan says",
        "operations plan", "crane plan", "protection plan",
        "section", "incident", "report",
        "per ", "per the", "according to", "reference",
        "lessons learned", "hazard register",
        "trade reference", "safe work",
        "company procedure", "project plan",
        "document", "documented", "documentation",
        "findings", "states that", "states:",
        "site safety", "the plan",
    ]
    markers_es = [
        "plan de seguridad", "plan del sitio", "plan cubre",
        "sección", "incidente", "reporte", "documento",
        "documentación", "según", "referencia", "lecciones",
        "procedimiento", "registro", "el plan",
    ]

    markers = markers_es if lang == "es" else markers_en
    return any(m in lower for m in markers)


@dataclass
class ScenarioResult:
    """Evaluation result for a single scenario."""
    scenario_id: int
    worker_name: str
    trade: str
    language_expected: str
    observation: str
    has_photo: bool

    # Response data
    response_text: str = ""
    response_mode: str = ""
    latency_ms: int = 0
    word_count: int = 0
    is_mock: bool = False
    model_used: str = ""

    # Documents
    doc_ids: list[int] = field(default_factory=list)
    doc_titles: list[str] = field(default_factory=list)

    # Hard rule results
    prohibited_found: list[str] = field(default_factory=list)
    technical_found: list[str] = field(default_factory=list)
    first_person_found: list[str] = field(default_factory=list)
    language_detected: str = "en"
    language_correct: bool = True
    attribution_present: bool = True

    # Soft criteria
    ends_with_question: bool = False
    name_used: bool = False

    @property
    def hard_pass(self) -> bool:
        return (
            not self.prohibited_found
            and not self.technical_found
            and not self.first_person_found
            and self.language_correct
            and self.attribution_present
        )


# ── Run a single scenario ────────────────────────────────────────────────

def run_scenario(db, scenario: dict, workers: dict, project) -> ScenarioResult:
    """Run one scenario through document retrieval + live Claude API."""
    worker = workers[scenario["worker"]]
    has_photo = scenario["has_photo"]

    # media_urls: use a non-HTTP sentinel so build_user_message skips the
    # image block but coach_live still sees has_photo=True.
    media_urls = ["photo_attached"] if has_photo else None

    # Step 1: Document retrieval
    doc_result = retrieve_relevant_documents(
        db=db,
        project_id=project.id,
        trade=worker.trade,
        observation_text=scenario["text"],
    )

    # Step 2: Call live Claude API
    profile = get_trade_profile(worker.trade)
    result = coach_live(
        observation=scenario["text"],
        trade=worker.trade,
        experience_level=worker.experience_level,
        media_urls=media_urls,
        turn_number=1,
        thread_history="",
        worker_tier=1,
        preferred_language=worker.preferred_language,
        mentor_notes="",
        document_context=doc_result.formatted_context,
        worker_name=worker.first_name,
        project_name=project.name,
        project_context=project.description or "",
    )

    # Step 3: Evaluate
    text = result.response_text
    lang_detected = detect_language(text)

    sr = ScenarioResult(
        scenario_id=scenario["id"],
        worker_name=worker.first_name,
        trade=worker.trade,
        language_expected=worker.preferred_language,
        observation=scenario["text"],
        has_photo=has_photo,
        response_text=text,
        response_mode=result.response_mode,
        latency_ms=result.latency_ms,
        word_count=len(text.split()),
        is_mock=result.is_mock,
        model_used=result.model_used,
        doc_ids=[d["id"] for d in doc_result.documents],
        doc_titles=[
            f"{d['title']} ({d['category']})"
            + (f" - {d['section_label']}" if d.get("section_label") else "")
            for d in doc_result.documents
        ],
        prohibited_found=check_prohibited_phrases(text),
        technical_found=check_technical_advice(text),
        first_person_found=check_first_person(text),
        language_detected=lang_detected,
        language_correct=(lang_detected == worker.preferred_language),
        attribution_present=check_document_attribution(
            text, [d["id"] for d in doc_result.documents], lang_detected,
            response_mode=result.response_mode,
        ),
        ends_with_question=text.rstrip().endswith("?"),
        name_used=(worker.first_name.lower() in text.lower()),
    )

    return sr


# ── Display helpers ──────────────────────────────────────────────────────

PASS = "[PASS]"
FAIL = "[FAIL]"
SOFT = "[SOFT]"
LINE = "=" * 72


def _safe_print(text: str) -> None:
    """Print text, replacing unencodable characters for Windows consoles."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_scenario(sr: ScenarioResult) -> None:
    """Print a single scenario result."""
    print()
    print(LINE)
    _safe_print(
        f"  Scenario {sr.scenario_id}/10: "
        f"{sr.worker_name} ({sr.trade}, {sr.language_expected})"
    )
    obs_display = sr.observation if len(sr.observation) <= 70 else sr.observation[:67] + "..."
    _safe_print(f'  "{obs_display}"')
    photo_label = "Yes" if sr.has_photo else "No"
    print(f"  Photo: {photo_label} | Docs found: {len(sr.doc_ids)}")
    print(LINE)

    if sr.is_mock:
        print("  ** WARNING: Fell back to MOCK mode (API error) **")

    print()
    print(f"  Response ({sr.response_mode}, {sr.latency_ms}ms, {sr.word_count} words):")
    # Wrap response text at ~70 chars
    words = sr.response_text.split()
    lines = []
    current = "  "
    for w in words:
        if len(current) + len(w) + 1 > 74:
            lines.append(current)
            current = "  " + w
        else:
            current += (" " if len(current) > 2 else "") + w
    if current.strip():
        lines.append(current)
    for line in lines:
        _safe_print(f"  {line}")

    if sr.doc_titles:
        print()
        print("  Documents retrieved:")
        for i, title in enumerate(sr.doc_titles, 1):
            _safe_print(f"    [{i}] {title}")

    print()
    print("  Evaluation:")

    # Hard rules
    if sr.prohibited_found:
        print(f"    {FAIL} Prohibited phrases: {sr.prohibited_found}")
    else:
        print(f"    {PASS} No prohibited phrases")

    if sr.technical_found:
        print(f"    {FAIL} Technical advice: {sr.technical_found}")
    else:
        print(f"    {PASS} No technical advice")

    if sr.first_person_found:
        print(f"    {FAIL} First-person: {sr.first_person_found}")
    else:
        print(f"    {PASS} No first-person constructions")

    if sr.language_correct:
        print(f"    {PASS} Language: {sr.language_detected} (expected: {sr.language_expected})")
    else:
        print(f"    {FAIL} Language: {sr.language_detected} (expected: {sr.language_expected})")

    if not sr.doc_ids:
        print(f"    {PASS} Document attribution: N/A (no docs retrieved)")
    elif sr.attribution_present:
        print(f"    {PASS} Document attribution present")
    else:
        print(f"    {FAIL} Document attribution MISSING (docs were retrieved)")

    # Soft criteria
    if sr.ends_with_question:
        print(f"    {PASS} Ends with question")
    else:
        print(f"    {SOFT} Does not end with question (soft)")

    if sr.name_used:
        print(f"    {PASS} Worker name used")
    else:
        print(f"    {SOFT} Worker name not used (soft)")

    if sr.word_count <= 40:
        print(f"    {PASS} Word count: {sr.word_count} (target: <=40)")
    else:
        print(f"    {SOFT} Word count: {sr.word_count} (target: <=40, soft)")

    # Verdict
    if sr.hard_pass:
        print(f"\n    Result: {PASS} PASS")
    else:
        print(f"\n    Result: {FAIL} FAIL")


def print_summary(results: list[ScenarioResult]) -> None:
    """Print final summary scorecard."""
    total = len(results)
    live_count = sum(1 for r in results if not r.is_mock)

    # Hard rule counts
    no_prohibited = sum(1 for r in results if not r.prohibited_found)
    no_technical = sum(1 for r in results if not r.technical_found)
    no_first_person = sum(1 for r in results if not r.first_person_found)
    lang_correct = sum(1 for r in results if r.language_correct)

    # Attribution: only count scenarios where docs were retrieved
    docs_scenarios = [r for r in results if r.doc_ids]
    docs_total = len(docs_scenarios)
    docs_attributed = sum(1 for r in docs_scenarios if r.attribution_present)

    # Soft criteria
    has_question = sum(1 for r in results if r.ends_with_question)
    name_used = sum(1 for r in results if r.name_used)
    word_ok = sum(1 for r in results if r.word_count <= 50)

    # Failed scenarios
    failed = [r for r in results if not r.hard_pass]

    # Timing
    total_latency = sum(r.latency_ms for r in results)
    avg_latency = total_latency // total if total else 0

    print()
    print()
    print(LINE)
    print("                        SUMMARY SCORECARD")
    print(LINE)
    print()
    print(f"  Scenarios run: {total}   |   Live API: {live_count}   |   "
          f"Mock fallback: {total - live_count}")
    print(f"  Total time: {total_latency / 1000:.1f}s   |   "
          f"Avg latency: {avg_latency}ms/scenario")
    print()

    def pct(n, d):
        return f"{n}/{d} ({100 * n // d}%)" if d else "N/A"

    def check(n, d):
        return PASS if d and n == d else FAIL

    print("  Hard Rules (must be 100%):")
    print(f"    {check(no_prohibited, total)} No prohibited phrases:    {pct(no_prohibited, total)}")
    print(f"    {check(no_technical, total)} No technical advice:      {pct(no_technical, total)}")
    print(f"    {check(no_first_person, total)} No first-person:          {pct(no_first_person, total)}")
    print(f"    {check(lang_correct, total)} Correct language:         {pct(lang_correct, total)}")
    if docs_total:
        print(f"    {check(docs_attributed, docs_total)} Document attribution:     {pct(docs_attributed, docs_total)}")
    else:
        print(f"    {PASS} Document attribution:     N/A (no docs retrieved)")

    print()
    print("  Soft Criteria:")
    q_mark = PASS if total and has_question / total >= 0.8 else SOFT
    n_mark = PASS if total and 0.25 <= name_used / total <= 0.35 else SOFT
    w_mark = PASS if total and word_ok / total >= 0.8 else SOFT
    print(f"    {q_mark} Ends with question:       {pct(has_question, total)}  (target: 80%+)")
    print(f"    {n_mark} Worker name used:         {pct(name_used, total)}  (target: 25-35%)")
    print(f"    {w_mark} Word count under 50:      {pct(word_ok, total)}  (target: 80%+)")

    if failed:
        print()
        print("  Failed scenarios:")
        for r in failed:
            reasons = []
            if r.prohibited_found:
                reasons.append(f"prohibited: {r.prohibited_found[:2]}")
            if r.technical_found:
                reasons.append(f"technical: {r.technical_found[:2]}")
            if r.first_person_found:
                reasons.append(f"first-person: {r.first_person_found[:2]}")
            if not r.language_correct:
                reasons.append(f"language: got {r.language_detected}, expected {r.language_expected}")
            if r.doc_ids and not r.attribution_present:
                reasons.append("missing doc attribution")
            print(f"    {FAIL} Scenario {r.scenario_id} ({r.worker_name}): {'; '.join(reasons)}")

    print()
    all_pass = all(r.hard_pass for r in results)
    if all_pass:
        print(f"  Overall: {PASS} PASS  —  All hard rules satisfied across {total} scenarios.")
    else:
        print(f"  Overall: {FAIL} FAIL  —  {len(failed)} scenario(s) violated hard rules.")
    print()


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print()
    print(LINE)
    _safe_print("  Safety as a Contact -- Live API Validation")
    print(f"  Document-grounded + behavioral reflection model")
    print(f"  {len(SCENARIOS)} scenarios against Claude Haiku")
    print(LINE)
    print()

    print("  Setting up database and seeding documents...", end=" ", flush=True)
    db, workers, project = setup_database()
    print("done.")
    print()

    results: list[ScenarioResult] = []

    for scenario in SCENARIOS:
        worker = workers[scenario["worker"]]
        print(
            f"  [{scenario['id']:2d}/10] {worker.first_name:6s} "
            f"({worker.trade:11s}) sending...",
            end=" ",
            flush=True,
        )

        start = time.monotonic()
        sr = run_scenario(db, scenario, workers, project)
        elapsed = time.monotonic() - start

        status = PASS if sr.hard_pass else FAIL
        mode_label = sr.response_mode or "?"
        print(
            f"{status} {mode_label:9s} {sr.latency_ms:5d}ms  "
            f"{sr.word_count:2d}w  "
            f"{'MOCK' if sr.is_mock else 'LIVE'}"
        )

        results.append(sr)

    # Detailed results
    for sr in results:
        print_scenario(sr)

    # Summary
    print_summary(results)

    db.close()


if __name__ == "__main__":
    main()
