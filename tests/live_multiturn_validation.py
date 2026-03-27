"""Multi-turn live API validation — tests conversation continuity and session management.

Seeds an in-memory database, then runs 3 multi-turn conversations (13 total turns)
through run_coaching() with the live Claude API. Validates per-turn hard rules plus
conversation-level session continuity, document variety, and mode variety.

Run:     python -m tests.live_multiturn_validation
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
    CoachingSession,
    Project,
    Worker,
    WorkerProfile,
    Observation,
    hash_phone,
    utcnow,
)
from backend.documents.ingestion import ingest_document
from backend.coaching.engine import run_coaching


# ── Prohibited phrases / technical / first-person (same as live_validation) ──

PROHIBITED_PHRASES = [
    "that setup looks unsafe", "that looks unsafe", "that's a hazard",
    "that is a hazard", "that needs to be fixed", "you need to",
    "you should", "make sure you", "i can see that", "i notice that",
    "it looks like", "i recommend", "i suggest", "i advise",
    "based on my experience", "in my experience", "from what i can see",
    "that's not right", "that's incorrect", "that's wrong",
    "that's dangerous", "that is dangerous", "that's a violation",
    "you're doing it wrong", "you need to fix", "you should fix",
    "you must", "you have to", "don't do that", "stop doing that",
    "that won't work", "that's not going to work",
    "here's what you should do", "let me tell you", "i think you should",
    "the correct way", "the right way", "the proper way",
    "i can tell", "i can see", "i see that", "looking at this",
    "what i see here", "i'm seeing", "it appears that",
    "clearly", "obviously",
    "you failed to", "you forgot to", "you missed", "you overlooked",
    "be careful", "osha requires", "safety first", "great job!",
    "remember to", "important to note", "best practice", "ensure that",
    "i noticed that", "based on the image",
    "your safety score", "your progress", "assessment",
    "what're", "how're", "where're",
    "i can", "i see", "i notice", "i think", "i would",
    "i'd ", "i'll", "i'm", "i've", "so i ", "let me",
]

TECHNICAL_PATTERNS = [
    "make sure the", "ensure the", "check the", "verify that",
    "always use", "never use", "you need a", "you'll want to",
    "the correct procedure is", "the sling angle should",
    "the bearing surface", "the load capacity",
    "rated for", "the minimum distance",
]

FIRST_PERSON_PATTERNS = [
    "i can", "i see", "i can see", "i notice", "i think",
    "i recommend", "i suggest", "i advise", "i'm seeing", "i can tell",
    "i would", "i'd ", "i'll", "i'm", "i've", "so i ", "let me", "in my",
]


# ── Conversations ────────────────────────────────────────────────────────

CONVERSATIONS = [
    {
        "id": "A",
        "label": "Jake: Guardrail hazard deepening",
        "worker": "jake",
        "turns": [
            {"text": "No guardrails on the east side of floor 9", "has_photo": True},
            {"text": "Talked to the foreman, he said they're coming but not til tomorrow", "has_photo": False},
            {"text": "Crew is still working out there near the edge though", "has_photo": True},
            {"text": "I put up some caution tape for now, that's all I had", "has_photo": False},
            {"text": "Anything in the safety plan about temporary barriers?", "has_photo": False},
        ],
    },
    {
        "id": "B",
        "label": "Miguel: Photo-first, gradual engagement",
        "worker": "miguel",
        "turns": [
            {"text": "\U0001f4f7", "has_photo": True},
            {"text": "La sierra", "has_photo": True},
            {"text": "No tiene la guarda puesta", "has_photo": True},
            {"text": "Le dije al capataz", "has_photo": False},
        ],
    },
    {
        "id": "C",
        "label": "Sarah: Positive obs turning to social feedback",
        "worker": "sarah",
        "turns": [
            {"text": "Level 12 housekeeping is really solid today, crew earned it", "has_photo": True},
            {"text": "Actually noticed the plumbers left some debris in the stairwell on 10 though", "has_photo": True},
            {"text": "Grabbed a photo of it, figured someone should see this", "has_photo": True},
            {"text": "Is this the kind of thing other projects are seeing too?", "has_photo": False},
        ],
    },
]


# ── Database setup (copied from live_validation.py) ──────────────────────

def setup_database():
    """Create in-memory SQLite database, seed company/project/workers/documents."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = SessionLocal()

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

    jake = Worker(
        phone_hash=hash_phone("+15551001001"),
        company_id=company.id, project_id=project.id,
        active_project_id=project.id, first_name="Jake",
        trade="ironworker", experience_level="intermediate",
        preferred_language="en",
    )
    miguel = Worker(
        phone_hash=hash_phone("+15551002002"),
        company_id=company.id, project_id=project.id,
        active_project_id=project.id, first_name="Miguel",
        trade="carpenter", experience_level="entry",
        preferred_language="es",
    )
    sarah = Worker(
        phone_hash=hash_phone("+15551003003"),
        company_id=company.id, project_id=project.id,
        active_project_id=project.id, first_name="Sarah",
        trade="electrician", experience_level="expert",
        preferred_language="en",
    )
    db.add_all([jake, miguel, sarah])
    db.commit()
    for w in [jake, miguel, sarah]:
        db.refresh(w)

    # 1. Site Safety Plan
    ingest_document(
        db, project_id=project.id,
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
        category="site_safety_plan", trade_tags=["all"],
        hazard_tags=["fall_protection", "housekeeping", "crane", "electrical", "excavation"],
    )

    # 2. Incident Report
    ingest_document(
        db, project_id=None,
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

    # 3. OSHA Standard
    ingest_document(
        db, project_id=None,
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
        category="osha_standard", trade_tags=["all"],
        hazard_tags=["fall_protection"],
    )

    # 4. Trade Reference -- Carpentry
    ingest_document(
        db, project_id=project.id,
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
Workers must use proper lifting techniques -- get help for loads over 50 lbs.""",
        category="trade_reference", trade_tags=["carpenter"],
        hazard_tags=["formwork", "saw_operations", "material_handling"],
    )

    # 5. Lessons Learned
    ingest_document(
        db, project_id=None,
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
        category="lessons_learned", trade_tags=["all"],
        hazard_tags=["heat_illness", "environmental"],
    )

    workers = {"jake": jake, "miguel": miguel, "sarah": sarah}
    return db, workers, project


# ── Evaluation helpers ───────────────────────────────────────────────────

def check_prohibited(text: str) -> list[str]:
    lower = text.lower()
    return [p for p in PROHIBITED_PHRASES if p in lower]


def check_technical(text: str) -> list[str]:
    lower = text.lower()
    return [p for p in TECHNICAL_PATTERNS if p in lower]


def check_first_person(text: str) -> list[str]:
    lower = text.lower()
    return [p for p in FIRST_PERSON_PATTERNS if p.strip() in lower]


def detect_language(text: str) -> str:
    words = text.lower().split()
    cleaned = [w.strip(".,!?\u00bf\u00a1()\"':-") for w in words]
    spanish = {
        "el", "la", "los", "las", "un", "una", "del", "con", "por", "para",
        "que", "tu", "su", "esta", "es", "hay", "como", "ya", "pero",
        "buena", "bueno", "foto", "zona", "equipo", "seguridad", "trabajo",
        "sitio", "plan", "algo", "otro", "otra", "esa", "ese",
    }
    english = {
        "the", "is", "are", "your", "you", "this", "that", "what", "how",
        "has", "have", "been", "was", "it", "for", "with", "from", "they",
        "who", "does", "got", "here", "there", "would", "about", "crew",
    }
    es = sum(1 for w in cleaned if w in spanish)
    en = sum(1 for w in cleaned if w in english)
    return "es" if es > en else "en"


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class TurnResult:
    turn_number: int
    observation: str
    has_photo: bool
    response_text: str = ""
    response_mode: str = ""
    latency_ms: int = 0
    word_count: int = 0
    is_mock: bool = False
    session_id: int | None = None
    doc_ids: list[int] = field(default_factory=list)
    prohibited_found: list[str] = field(default_factory=list)
    technical_found: list[str] = field(default_factory=list)
    first_person_found: list[str] = field(default_factory=list)
    language_detected: str = "en"
    language_correct: bool = True
    ends_with_question: bool = False
    name_used: bool = False

    @property
    def hard_pass(self) -> bool:
        return (
            not self.prohibited_found
            and not self.technical_found
            and not self.first_person_found
            and self.language_correct
        )


@dataclass
class ConversationResult:
    conv_id: str
    label: str
    worker_name: str
    trade: str
    language_expected: str
    turns: list[TurnResult] = field(default_factory=list)
    # Conversation-level checks
    session_continuous: bool = False
    turns_correct: bool = False
    doc_variety: bool = False
    mode_variety: bool = False
    no_repeats: bool = False
    profile_exists: bool = False
    profile_turns: int = 0


# ── Display ──────────────────────────────────────────────────────────────

PASS = "[PASS]"
FAIL = "[FAIL]"
SOFT = "[SOFT]"
LINE = "=" * 72
THIN = "-" * 72


def _safe(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_conversation(cr: ConversationResult) -> None:
    """Print full thread + per-turn grid + conversation checks."""
    print()
    print(LINE)
    _safe(f"  Conversation {cr.conv_id}: {cr.label}")
    _safe(f"  Worker: {cr.worker_name} ({cr.trade}, {cr.language_expected})")
    print(f"  Turns: {len(cr.turns)}")
    print(LINE)

    # Full thread
    print()
    print("  THREAD:")
    for t in cr.turns:
        photo_tag = " [photo]" if t.has_photo else ""
        obs_display = t.observation if len(t.observation) <= 60 else t.observation[:57] + "..."
        _safe(f"    [{cr.worker_name} T{t.turn_number}]{photo_tag} {obs_display}")
        _safe(f"    [Coach T{t.turn_number}] ({t.response_mode}, {t.word_count}w, {t.latency_ms}ms)")
        # Wrap response
        words = t.response_text.split()
        cur = "      "
        for w in words:
            if len(cur) + len(w) + 1 > 76:
                _safe(cur)
                cur = "      " + w
            else:
                cur += (" " if len(cur) > 6 else "") + w
        if cur.strip():
            _safe(cur)
        print()

    # Per-turn evaluation grid
    print(THIN)
    print("  PER-TURN EVALUATION:")
    print(f"  {'Turn':>4s}  {'Mode':9s}  {'Words':>5s}  {'Prohib':6s}  {'Tech':6s}  {'1stPer':6s}  "
          f"{'Lang':6s}  {'Quest':5s}  {'Name':4s}  {'Result':6s}")
    print(f"  {'----':>4s}  {'---------':9s}  {'-----':>5s}  {'------':6s}  {'------':6s}  {'------':6s}  "
          f"{'------':6s}  {'-----':5s}  {'----':4s}  {'------':6s}")
    for t in cr.turns:
        prohib = "ok" if not t.prohibited_found else "FAIL"
        tech = "ok" if not t.technical_found else "FAIL"
        fp = "ok" if not t.first_person_found else "FAIL"
        lang = "ok" if t.language_correct else "FAIL"
        quest = "?" if t.ends_with_question else "."
        name = "Y" if t.name_used else "-"
        result = "PASS" if t.hard_pass else "FAIL"
        print(f"  {t.turn_number:4d}  {t.response_mode:9s}  {t.word_count:5d}  {prohib:6s}  "
              f"{tech:6s}  {fp:6s}  {lang:6s}  {quest:>5s}  {name:>4s}  {result:6s}")

    # Conversation-level checks
    print()
    print("  CONVERSATION CHECKS:")
    mark = lambda b: PASS if b else FAIL
    session_ids = [t.session_id for t in cr.turns]
    print(f"    {mark(cr.session_continuous)} Session continuity: "
          f"{'all same ID (' + str(session_ids[0]) + ')' if cr.session_continuous else 'BROKEN ' + str(session_ids)}")
    expected_turns = list(range(1, len(cr.turns) + 1))
    actual_turns = [t.turn_number for t in cr.turns]
    print(f"    {mark(cr.turns_correct)} Turn counting: "
          f"{'correct ' + str(actual_turns) if cr.turns_correct else 'WRONG ' + str(actual_turns) + ' expected ' + str(expected_turns)}")
    all_doc_ids = set()
    for t in cr.turns:
        all_doc_ids.update(t.doc_ids)
    modes = set(t.response_mode for t in cr.turns)
    print(f"    {mark(cr.doc_variety)} Document variety: "
          f"{len(all_doc_ids)} unique doc(s) referenced, modes: {modes}")
    print(f"    {mark(cr.mode_variety)} Response mode variety: {modes}")
    print(f"    {mark(cr.no_repeats)} No repeated responses")
    print(f"    {mark(cr.profile_exists)} Worker profile exists "
          f"(total_turns={cr.profile_turns})")

    # Print hard-rule failures
    failed_turns = [t for t in cr.turns if not t.hard_pass]
    if failed_turns:
        print()
        print("  HARD RULE FAILURES:")
        for t in failed_turns:
            reasons = []
            if t.prohibited_found:
                reasons.append(f"prohibited: {t.prohibited_found[:2]}")
            if t.technical_found:
                reasons.append(f"technical: {t.technical_found[:2]}")
            if t.first_person_found:
                reasons.append(f"first-person: {t.first_person_found[:2]}")
            if not t.language_correct:
                reasons.append(f"lang: {t.language_detected} != {cr.language_expected}")
            print(f"    {FAIL} Turn {t.turn_number}: {'; '.join(reasons)}")


def print_summary(conversations: list[ConversationResult]) -> None:
    all_turns = [t for c in conversations for t in c.turns]
    total = len(all_turns)
    live = sum(1 for t in all_turns if not t.is_mock)
    total_ms = sum(t.latency_ms for t in all_turns)

    no_prohib = sum(1 for t in all_turns if not t.prohibited_found)
    no_tech = sum(1 for t in all_turns if not t.technical_found)
    no_fp = sum(1 for t in all_turns if not t.first_person_found)
    lang_ok = sum(1 for t in all_turns if t.language_correct)
    has_q = sum(1 for t in all_turns if t.ends_with_question)
    word_ok = sum(1 for t in all_turns if t.word_count <= 40)

    def pct(n, d):
        return f"{n}/{d} ({100 * n // d}%)" if d else "N/A"
    def chk(n, d):
        return PASS if d and n == d else FAIL

    print()
    print()
    print(LINE)
    print("                    MULTI-TURN SUMMARY SCORECARD")
    print(LINE)
    print()
    print(f"  Conversations: {len(conversations)}   |   Total turns: {total}   |   "
          f"Live API: {live}   |   Mock: {total - live}")
    print(f"  Total time: {total_ms / 1000:.1f}s   |   Avg latency: {total_ms // total if total else 0}ms/turn")
    print()

    print("  Hard Rules (per-turn, must be 100%):")
    print(f"    {chk(no_prohib, total)} No prohibited phrases:    {pct(no_prohib, total)}")
    print(f"    {chk(no_tech, total)} No technical advice:      {pct(no_tech, total)}")
    print(f"    {chk(no_fp, total)} No first-person:          {pct(no_fp, total)}")
    print(f"    {chk(lang_ok, total)} Correct language:         {pct(lang_ok, total)}")

    print()
    print("  Soft Criteria (per-turn):")
    q_mark = PASS if total and has_q / total >= 0.7 else SOFT
    w_mark = PASS if total and word_ok / total >= 0.7 else SOFT
    print(f"    {q_mark} Ends with question:       {pct(has_q, total)}  (target: 70%+)")
    print(f"    {w_mark} Word count under 40:      {pct(word_ok, total)}  (target: 70%+)")

    print()
    print("  Conversation-Level Checks:")
    for c in conversations:
        all_conv_pass = (c.session_continuous and c.turns_correct and c.doc_variety
                         and c.mode_variety and c.no_repeats and c.profile_exists)
        mark = PASS if all_conv_pass else FAIL
        failures = []
        if not c.session_continuous: failures.append("session")
        if not c.turns_correct: failures.append("turns")
        if not c.doc_variety: failures.append("doc variety")
        if not c.mode_variety: failures.append("mode variety")
        if not c.no_repeats: failures.append("repeats")
        if not c.profile_exists: failures.append("profile")
        detail = " -- " + ", ".join(failures) if failures else ""
        print(f"    {mark} Conv {c.conv_id} ({c.worker_name}){detail}")

    all_hard = all(t.hard_pass for t in all_turns)
    all_conv = all(
        c.session_continuous and c.turns_correct and c.doc_variety
        and c.mode_variety and c.no_repeats and c.profile_exists
        for c in conversations
    )
    print()
    if all_hard and all_conv:
        print(f"  Overall: {PASS} PASS  --  All hard rules + conversation checks satisfied.")
    elif all_hard:
        print(f"  Overall: {SOFT} PARTIAL  --  Hard rules pass, but conversation-level issues found.")
    else:
        failed_count = sum(1 for t in all_turns if not t.hard_pass)
        print(f"  Overall: {FAIL} FAIL  --  {failed_count} turn(s) violated hard rules.")
    print()


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    total_turns = sum(len(c["turns"]) for c in CONVERSATIONS)

    print()
    print(LINE)
    _safe("  Safety as a Contact -- Multi-Turn Live Validation")
    print(f"  {len(CONVERSATIONS)} conversations, {total_turns} total turns against Claude Haiku")
    print(LINE)
    print()

    print("  Setting up database and seeding documents...", end=" ", flush=True)
    db, workers, project = setup_database()
    print("done.")
    print()

    conversation_results: list[ConversationResult] = []

    for conv in CONVERSATIONS:
        worker = workers[conv["worker"]]
        _safe(f"  --- Conversation {conv['id']}: {conv['label']} ---")

        cr = ConversationResult(
            conv_id=conv["id"],
            label=conv["label"],
            worker_name=worker.first_name,
            trade=worker.trade,
            language_expected=worker.preferred_language,
        )

        for i, turn in enumerate(conv["turns"]):
            turn_num = i + 1
            has_photo = turn["has_photo"]
            media_urls = ["photo_attached"] if has_photo else None
            photo_tag = " [photo]" if has_photo else ""

            # Create observation record
            obs = Observation(
                worker_id=worker.id,
                project_id=project.id,
                raw_text=turn["text"],
                media_urls=json.dumps(media_urls or []),
            )
            db.add(obs)
            db.commit()
            db.refresh(obs)

            print(
                f"    T{turn_num}/{len(conv['turns'])}{photo_tag:8s} sending...",
                end=" ", flush=True,
            )

            result = run_coaching(
                db,
                observation_text=turn["text"],
                trade=worker.trade,
                experience_level=worker.experience_level,
                observation_id=obs.id,
                media_urls=media_urls,
                phone_hash=worker.phone_hash,
                worker_id=worker.id,
                preferred_language=worker.preferred_language,
            )

            text = result.response_text
            lang = detect_language(text)

            tr = TurnResult(
                turn_number=result.turn_number,
                observation=turn["text"],
                has_photo=has_photo,
                response_text=text,
                response_mode=result.response_mode,
                latency_ms=result.latency_ms,
                word_count=len(text.split()),
                is_mock=result.is_mock,
                session_id=result.session_id,
                doc_ids=result.document_ids,
                prohibited_found=check_prohibited(text),
                technical_found=check_technical(text),
                first_person_found=check_first_person(text),
                language_detected=lang,
                language_correct=(lang == worker.preferred_language),
                ends_with_question=text.rstrip().endswith("?"),
                name_used=(worker.first_name.lower() in text.lower()),
            )
            cr.turns.append(tr)

            status = PASS if tr.hard_pass else FAIL
            print(
                f"{status} T{tr.turn_number} {tr.response_mode:9s} "
                f"{tr.latency_ms:5d}ms {tr.word_count:2d}w "
                f"{'MOCK' if tr.is_mock else 'LIVE'}"
            )

            # 1-second pause between turns
            if turn_num < len(conv["turns"]):
                time.sleep(1)

        # ── Conversation-level checks ──
        session_ids = [t.session_id for t in cr.turns]
        cr.session_continuous = len(set(session_ids)) == 1 and session_ids[0] is not None

        actual_turn_nums = [t.turn_number for t in cr.turns]
        expected_turn_nums = list(range(1, len(cr.turns) + 1))
        cr.turns_correct = actual_turn_nums == expected_turn_nums

        all_doc_ids = set()
        for t in cr.turns:
            all_doc_ids.update(t.doc_ids)
        modes = set(t.response_mode for t in cr.turns)
        cr.doc_variety = len(all_doc_ids) >= 2 or len(modes) >= 2

        cr.mode_variety = len(modes) >= 2

        responses = [t.response_text for t in cr.turns]
        cr.no_repeats = len(responses) == len(set(responses))

        profile = (
            db.query(WorkerProfile)
            .filter(WorkerProfile.phone_hash == worker.phone_hash)
            .first()
        )
        cr.profile_exists = profile is not None
        cr.profile_turns = profile.total_turns if profile else 0

        conversation_results.append(cr)
        print()

    # ── Detailed output ──
    for cr in conversation_results:
        print_conversation(cr)

    # ── Summary ──
    print_summary(conversation_results)

    db.close()


if __name__ == "__main__":
    main()
