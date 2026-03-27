"""Live API validation with REAL Wollam safety documents.

Uses the ingested Wollam Safety Program + Valar Ward 250 SSSP instead of
seed documents. Validates that coaching responses cite real company content.

Prerequisites: python -m scripts.ingest_wollam_docs (populates wollam_docs.db)
Run:           python -m tests.live_real_docs_validation
Requires:      ANTHROPIC_API_KEY environment variable
"""

import os
import sys
from pathlib import Path

# ── Pre-flight: load .env if needed ──────────────────────────────────────
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
    WorkerProfile,
    SafetyDocument,
    Observation,
    hash_phone,
    utcnow,
)
from backend.coaching.engine import run_coaching


# ── Check lists (same as live_validation.py) ─────────────────────────────

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


# ── Scenarios ────────────────────────────────────────────────────────────

SCENARIOS = [
    {
        "id": 1, "worker": "jake",
        "text": "Crane picking a load near the excavation, no tag lines",
        "has_photo": True,
    },
    {
        "id": 2, "worker": "jake",
        "text": "Guy near the trench and it looks deep, not sure about the shoring",
        "has_photo": True,
    },
    {
        "id": 3, "worker": "miguel",
        "text": "Mira, no hay barandilla aqui",
        "has_photo": True,
    },
    {
        "id": 4, "worker": "miguel",
        "text": "Hace mucho calor hoy, necesitamos agua",
        "has_photo": True,
    },
    {
        "id": 5, "worker": "sarah",
        "text": "Open panel, no lockout tagout on it",
        "has_photo": True,
    },
    {
        "id": 6, "worker": "sarah",
        "text": "New guy started today, first week on site",
        "has_photo": False,
    },
    {
        "id": 7, "worker": "jake",
        "text": "Housekeeping on level 3 is a mess, debris everywhere",
        "has_photo": True,
    },
    {
        "id": 8, "worker": "miguel",
        "text": "\U0001f4f7",
        "has_photo": True,
    },
    {
        "id": 9, "worker": "sarah",
        "text": "Someone's not wearing their hard hat in the work area",
        "has_photo": True,
    },
    {
        "id": 10, "worker": "jake",
        "text": "Toolbox talk this morning was about stop work authority",
        "has_photo": False,
    },
]


# ── Database setup ───────────────────────────────────────────────────────

def setup_database():
    """Connect to the wollam_docs.db and add worker records for testing."""
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "data" / "wollam_docs.db"

    if not db_path.exists():
        print()
        print("  ERROR: wollam_docs.db not found.")
        print("  Run first: python -m scripts.ingest_wollam_docs")
        sys.exit(1)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = SessionLocal()

    # Verify documents exist
    doc_count = db.query(SafetyDocument).count()
    if doc_count == 0:
        print("  ERROR: No documents in database. Run ingest_wollam_docs first.")
        sys.exit(1)

    # Get company and project
    company = db.query(Company).filter(Company.name == "Wollam Construction").first()
    project = db.query(Project).filter(Project.name == "Valar Ward 250").first()
    if not company or not project:
        print("  ERROR: Company/Project not found. Re-run ingest_wollam_docs.")
        sys.exit(1)

    # Create test workers (idempotent — check by phone_hash)
    workers_data = [
        ("jake", "+15551001001", "Jake", "ironworker", "intermediate", "en"),
        ("miguel", "+15551002002", "Miguel", "carpenter", "entry", "es"),
        ("sarah", "+15551003003", "Sarah", "electrician", "expert", "en"),
    ]
    workers = {}
    for key, phone, name, trade, exp, lang in workers_data:
        ph = hash_phone(phone)
        w = db.query(Worker).filter(Worker.phone_hash == ph).first()
        if not w:
            w = Worker(
                phone_hash=ph,
                company_id=company.id,
                project_id=project.id,
                active_project_id=project.id,
                first_name=name,
                trade=trade,
                experience_level=exp,
                preferred_language=lang,
            )
            db.add(w)
            db.commit()
            db.refresh(w)
        workers[key] = w

    return db, workers, project, doc_count


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

def check_real_doc_attribution(text: str, doc_ids: list[int], response_mode: str) -> bool:
    """Check if the response cites real Wollam/Valar content (not seed docs)."""
    if not doc_ids:
        return True
    if response_mode in ("reflect", "connect"):
        return True
    lower = text.lower()
    real_markers = [
        "wollam", "valar", "ward 250", "sssp",
        "safety program", "site safety plan", "site-specific",
        "safety plan", "plan says", "plan states", "plan requires",
        "plan covers", "section", "the plan",
        "per the", "according to", "documented",
        # Spanish attribution markers
        "plan de seguridad", "el plan", "plan del sitio",
        "plan cubre", "documentado", "documento",
    ]
    return any(m in lower for m in real_markers)


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class TurnResult:
    scenario_id: int
    worker_name: str
    trade: str
    language_expected: str
    observation: str
    has_photo: bool
    response_text: str = ""
    response_mode: str = ""
    latency_ms: int = 0
    word_count: int = 0
    is_mock: bool = False
    doc_ids: list[int] = field(default_factory=list)
    doc_titles: list[str] = field(default_factory=list)
    prohibited_found: list[str] = field(default_factory=list)
    technical_found: list[str] = field(default_factory=list)
    first_person_found: list[str] = field(default_factory=list)
    language_detected: str = "en"
    language_correct: bool = True
    attribution_real: bool = True
    ends_with_question: bool = False
    name_used: bool = False

    @property
    def hard_pass(self) -> bool:
        return (
            not self.prohibited_found
            and not self.technical_found
            and not self.first_person_found
            and self.language_correct
            and self.attribution_real
        )


# ── Display ──────────────────────────────────────────────────────────────

PASS = "[PASS]"
FAIL = "[FAIL]"
SOFT = "[SOFT]"
LINE = "=" * 72


def _safe(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def print_result(tr: TurnResult) -> None:
    print()
    print(LINE)
    _safe(f"  Scenario {tr.scenario_id}/10: {tr.worker_name} ({tr.trade}, {tr.language_expected})")
    obs = tr.observation if len(tr.observation) <= 65 else tr.observation[:62] + "..."
    _safe(f'  "{obs}"')
    print(f"  Photo: {'Yes' if tr.has_photo else 'No'} | Docs: {len(tr.doc_ids)}")
    print(LINE)

    if tr.is_mock:
        print("  ** WARNING: MOCK mode (API error) **")

    print(f"\n  Response ({tr.response_mode}, {tr.latency_ms}ms, {tr.word_count}w):")
    words = tr.response_text.split()
    cur = "    "
    for w in words:
        if len(cur) + len(w) + 1 > 76:
            _safe(cur)
            cur = "    " + w
        else:
            cur += (" " if len(cur) > 4 else "") + w
    if cur.strip():
        _safe(cur)

    if tr.doc_titles:
        print("\n  Documents retrieved:")
        for i, t in enumerate(tr.doc_titles, 1):
            _safe(f"    [{i}] {t}")

    print("\n  Evaluation:")
    print(f"    {PASS if not tr.prohibited_found else FAIL} Prohibited phrases"
          + (f": {tr.prohibited_found[:2]}" if tr.prohibited_found else ""))
    print(f"    {PASS if not tr.technical_found else FAIL} Technical advice"
          + (f": {tr.technical_found[:2]}" if tr.technical_found else ""))
    print(f"    {PASS if not tr.first_person_found else FAIL} First-person"
          + (f": {tr.first_person_found[:2]}" if tr.first_person_found else ""))
    print(f"    {PASS if tr.language_correct else FAIL} Language: {tr.language_detected} "
          f"(expected: {tr.language_expected})")
    print(f"    {PASS if tr.attribution_real else FAIL} Real doc attribution"
          + ("" if tr.attribution_real else " (cites seed/unknown docs)"))
    print(f"    {PASS if tr.ends_with_question else SOFT} Ends with question")
    print(f"    {PASS if tr.name_used else SOFT} Worker name used")
    wc_ok = tr.word_count <= 40
    print(f"    {PASS if wc_ok else SOFT} Word count: {tr.word_count} (target: <=40)")
    print(f"\n    Result: {PASS if tr.hard_pass else FAIL} {'PASS' if tr.hard_pass else 'FAIL'}")


def print_summary(results: list[TurnResult]) -> None:
    total = len(results)
    live = sum(1 for r in results if not r.is_mock)
    ms = sum(r.latency_ms for r in results)

    no_p = sum(1 for r in results if not r.prohibited_found)
    no_t = sum(1 for r in results if not r.technical_found)
    no_f = sum(1 for r in results if not r.first_person_found)
    lang = sum(1 for r in results if r.language_correct)
    attr = sum(1 for r in results if r.attribution_real)
    quest = sum(1 for r in results if r.ends_with_question)
    wc = sum(1 for r in results if r.word_count <= 40)
    failed = [r for r in results if not r.hard_pass]

    def pct(n, d):
        return f"{n}/{d} ({100 * n // d}%)" if d else "N/A"
    def chk(n, d):
        return PASS if d and n == d else FAIL

    print("\n\n" + LINE)
    print("               REAL DOCS VALIDATION SCORECARD")
    print(LINE)
    print(f"\n  Scenarios: {total}  |  Live: {live}  |  Mock: {total - live}")
    print(f"  Time: {ms / 1000:.1f}s  |  Avg: {ms // total if total else 0}ms/scenario")
    print(f"\n  Hard Rules (must be 100%):")
    print(f"    {chk(no_p, total)} No prohibited phrases:    {pct(no_p, total)}")
    print(f"    {chk(no_t, total)} No technical advice:      {pct(no_t, total)}")
    print(f"    {chk(no_f, total)} No first-person:          {pct(no_f, total)}")
    print(f"    {chk(lang, total)} Correct language:         {pct(lang, total)}")
    print(f"    {chk(attr, total)} Real doc attribution:     {pct(attr, total)}")

    print(f"\n  Soft Criteria:")
    print(f"    {PASS if quest / total >= 0.8 else SOFT} Ends with question:       {pct(quest, total)}")
    print(f"    {PASS if wc / total >= 0.7 else SOFT} Word count under 40:      {pct(wc, total)}")

    if failed:
        print(f"\n  Failed scenarios:")
        for r in failed:
            reasons = []
            if r.prohibited_found: reasons.append(f"prohibited: {r.prohibited_found[:2]}")
            if r.technical_found: reasons.append(f"technical: {r.technical_found[:2]}")
            if r.first_person_found: reasons.append(f"1st person: {r.first_person_found[:2]}")
            if not r.language_correct: reasons.append(f"lang: {r.language_detected}")
            if not r.attribution_real: reasons.append("no real doc attribution")
            print(f"    {FAIL} Scenario {r.scenario_id} ({r.worker_name}): {'; '.join(reasons)}")

    all_pass = all(r.hard_pass for r in results)
    print(f"\n  Overall: {PASS if all_pass else FAIL} "
          f"{'PASS' if all_pass else 'FAIL -- ' + str(len(failed)) + ' scenario(s) failed'}")
    print()


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print()
    print(LINE)
    _safe("  Safety as a Contact -- Real Document Validation")
    print(f"  10 scenarios against Claude Haiku with real Wollam docs")
    print(LINE)
    print()

    print("  Connecting to wollam_docs.db...", end=" ", flush=True)
    db, workers, project, doc_count = setup_database()
    print(f"done. ({doc_count} documents)")
    print()

    results: list[TurnResult] = []

    for scenario in SCENARIOS:
        worker = workers[scenario["worker"]]
        has_photo = scenario["has_photo"]
        media_urls = ["photo_attached"] if has_photo else None

        print(
            f"  [{scenario['id']:2d}/10] {worker.first_name:6s} ({worker.trade:11s}) sending...",
            end=" ", flush=True,
        )

        # Create observation
        obs = Observation(
            worker_id=worker.id,
            project_id=project.id,
            raw_text=scenario["text"],
            media_urls=json.dumps(media_urls or []),
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)

        result = run_coaching(
            db,
            observation_text=scenario["text"],
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
            doc_ids=result.document_ids,
            doc_titles=[
                f"{d['title']} ({d['category']})"
                + (f" - {d['section_label']}" if d.get("section_label") else "")
                for d in (
                    db.query(SafetyDocument)
                    .filter(SafetyDocument.id.in_(result.document_ids))
                    .all()
                    if result.document_ids else []
                )
                for d in [{"title": d.title, "category": d.category,
                           "section_label": d.section_label}]
            ],
            prohibited_found=check_prohibited(text),
            technical_found=check_technical(text),
            first_person_found=check_first_person(text),
            language_detected=lang,
            language_correct=(lang == worker.preferred_language),
            attribution_real=check_real_doc_attribution(
                text, result.document_ids, result.response_mode,
            ),
            ends_with_question=text.rstrip().endswith("?"),
            name_used=(worker.first_name.lower() in text.lower()),
        )

        results.append(tr)

        status = PASS if tr.hard_pass else FAIL
        print(f"{status} {tr.response_mode:9s} {tr.latency_ms:5d}ms {tr.word_count:2d}w "
              f"docs={len(tr.doc_ids)} {'MOCK' if tr.is_mock else 'LIVE'}")

    for tr in results:
        print_result(tr)

    print_summary(results)
    db.close()


if __name__ == "__main__":
    main()
