"""Ingest Wollam safety documents from PDF into the document database.

Extracts text from two real safety PDFs, cleans them, splits into sections,
auto-tags hazard categories, and feeds into the existing ingest_document() pipeline.

Run:     python -m scripts.ingest_wollam_docs [--db-path PATH]
Default: project/data/wollam_docs.db
"""

import argparse
import os
import sys
from pathlib import Path

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT.parent / "Sample Safety Plans"

WOLLAM_PDF = SAMPLE_DIR / "Wollam Safety Program 2024 Rev. 1.4.pdf"
VALAR_PDF = SAMPLE_DIR / "VALAR WARD 250 PROJECT SSSP DRAFT 2025.11.10 (002).pdf"


# ── Hazard tag auto-detection ────────────────────────────────────────────

HAZARD_TAG_RULES: dict[str, list[str]] = {
    "fall_protection": [
        "fall protection", "fall arrest", "guardrail", "harness",
        "tie-off", "tie off", "leading edge", "safety net",
        "personal fall", "anchor point", "lifeline",
    ],
    "excavation": [
        "excavation", "trench", "shoring", "cave-in", "cave in",
        "competent person", "spoil pile", "protective system",
    ],
    "crane": [
        "crane", "rigging", "lift plan", "tag line", "tagline",
        "signal person", "suspended load", "critical lift",
    ],
    "ppe": [
        "ppe", "personal protective", "hard hat", "safety glasses",
        "high-visibility", "hi-vis", "hearing protection",
        "steel-toe", "steel toe", "respirator", "face shield",
    ],
    "housekeeping": [
        "housekeeping", "debris", "staging area", "material storage",
        "work area clean",
    ],
    "heat_illness": [
        "heat illness", "heat stress", "hydration", "acclimatization",
        "heat stroke", "heat exhaustion", "cool down", "cool-down",
        "heat index", "shade", "water rest",
    ],
    "cold_weather": [
        "cold weather", "winter safety", "frostbite", "hypothermia",
        "wind chill", "cold stress",
    ],
    "electrical": [
        "electrical safety", "lockout", "tagout", "loto",
        "energized", "gfci", "arc flash", "de-energize",
    ],
    "fire": [
        "fire fighting", "fire extinguisher", "flammable",
        "hot work", "fire prevention", "fire protection",
    ],
    "ergonomic": [
        "lifting", "ergonomic", "manual handling", "back injury",
        "50 lbs", "material handling", "proper lifting",
    ],
    "driving": [
        "driving safety", "vehicle safety", "fleet", "seatbelt",
        "motor vehicle", "distracted driving", "speed limit",
    ],
    "hazmat": [
        "hazardous material", "hazardous substance", "chemical",
        "sds", "msds", "spill", "hazcom",
    ],
    "incident_reporting": [
        "incident report", "incident investigation", "root cause",
        "corrective action", "near miss", "near-miss",
    ],
    "hand_safety": [
        "hand safety", "hand injury", "laceration", "pinch point",
        "glove selection", "hand protection",
    ],
    "emergency": [
        "emergency action", "emergency preparedness", "evacuation",
        "crisis management", "assembly point", "first aid",
        "emergency response",
    ],
    "confined_space": [
        "confined space", "permit-required", "atmospheric testing",
        "entry permit",
    ],
    "scaffold": [
        "scaffold", "scaffolding", "competent person scaffold",
    ],
    "silica": [
        "silica", "crystalline silica", "respirable dust",
    ],
    "struck_by": [
        "struck-by", "struck by", "dropped object", "falling object",
    ],
}


def detect_hazard_tags(content: str) -> list[str]:
    """Scan section content and return matching hazard tags."""
    lower = content.lower()
    tags = []
    for tag, keywords in HAZARD_TAG_RULES.items():
        if any(kw in lower for kw in keywords):
            tags.append(tag)
    return tags if tags else ["administrative"]


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest Wollam safety PDFs")
    parser.add_argument(
        "--db-path",
        default=str(PROJECT_ROOT / "data" / "wollam_docs.db"),
        help="SQLite database path (default: project/data/wollam_docs.db)",
    )
    parser.add_argument(
        "--use-env-db",
        action="store_true",
        help="Use DATABASE_URL from environment instead of --db-path (for PostgreSQL)",
    )
    args = parser.parse_args()

    # Verify PDFs exist
    for pdf in [WOLLAM_PDF, VALAR_PDF]:
        if not pdf.exists():
            print(f"  ERROR: PDF not found: {pdf}")
            sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base
    from backend.models import Company, Project, SafetyDocument
    from backend.documents.ingestion import ingest_document
    from backend.documents.pdf_extractor import (
        extract_pdf_text,
        WOLLAM_HEADER_PATTERN,
    )

    # Set up database — either from env var or SQLite path
    if args.use_env_db:
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            print("  ERROR: --use-env-db requires DATABASE_URL environment variable")
            sys.exit(1)
        engine = create_engine(db_url, pool_pre_ping=True)
        db_label = db_url.split("@")[-1].split("/")[0] if "@" in db_url else db_url
    else:
        db_path = Path(args.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        from backend.config import Settings
        settings = Settings()
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        db_label = str(db_path)

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = SessionLocal()

    print()
    print("=" * 60)
    print("  Wollam Safety Document Ingestion")
    print("=" * 60)
    print(f"  Database: {db_label}")
    print()

    # ── Company ──
    company = db.query(Company).filter(Company.name == "Wollam Construction").first()
    if not company:
        company = Company(name="Wollam Construction")
        db.add(company)
        db.commit()
        db.refresh(company)
        print("  Created company: Wollam Construction")
    else:
        print("  Found existing company: Wollam Construction")

    # ── Project ──
    project = db.query(Project).filter(Project.name == "Valar Ward 250").first()
    if not project:
        project = Project(
            company_id=company.id,
            name="Valar Ward 250",
            location="Kiewit project site",
            description=(
                "Valar Atomics facility construction. "
                "Top hazards: human-equipment interaction, "
                "trenching & excavation, crane operations."
            ),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        print("  Created project: Valar Ward 250")
    else:
        print("  Found existing project: Valar Ward 250")

    print()

    # ── Ingest Wollam Safety Program ──
    wollam_title = "Wollam Safety Program Rev 1.4"
    print(f"  Extracting: {WOLLAM_PDF.name}...")
    wollam_text = extract_pdf_text(
        str(WOLLAM_PDF),
        skip_pages=[1, 2, 3, 4, 5],
        header_pattern=WOLLAM_HEADER_PATTERN,
    )
    print(f"    Extracted {len(wollam_text)} chars, {len(wollam_text.splitlines())} lines")

    # Idempotency: clear old docs for this title
    old_count = db.query(SafetyDocument).filter(
        SafetyDocument.title == wollam_title
    ).delete()
    if old_count:
        db.commit()
        print(f"    Cleared {old_count} existing sections")

    # Split into major sections (top-level X.0 sections) for better tagging
    # We'll ingest each top-level section as a separate document with its own hazard tags
    wollam_docs = _ingest_by_top_sections(
        db=db,
        full_text=wollam_text,
        title=wollam_title,
        category="company_procedure",
        project_id=None,
        trade_tags=["all"],
    )
    print(f"    Ingested {len(wollam_docs)} sections")

    # ── Ingest Valar Ward 250 SSSP ──
    valar_title = "Valar Ward 250 SSSP"
    print()
    print(f"  Extracting: {VALAR_PDF.name}...")
    valar_text = extract_pdf_text(
        str(VALAR_PDF),
        skip_pages=[1, 2, 3, 4],
    )
    print(f"    Extracted {len(valar_text)} chars, {len(valar_text.splitlines())} lines")

    # Idempotency: clear old docs for this title
    old_count = db.query(SafetyDocument).filter(
        SafetyDocument.title == valar_title
    ).delete()
    if old_count:
        db.commit()
        print(f"    Cleared {old_count} existing sections")

    valar_docs = _ingest_by_top_sections(
        db=db,
        full_text=valar_text,
        title=valar_title,
        category="site_safety_plan",
        project_id=project.id,
        trade_tags=["all"],
    )
    print(f"    Ingested {len(valar_docs)} sections")

    # ── Summary ──
    total = db.query(SafetyDocument).count()
    print()
    print("-" * 60)
    print(f"  Total documents in database: {total}")
    print(f"    Wollam Safety Program: {len(wollam_docs)} sections")
    print(f"    Valar Ward 250 SSSP:  {len(valar_docs)} sections")
    print(f"  Database: {db_label}")
    print()

    db.close()


def _ingest_by_top_sections(
    db,
    full_text: str,
    title: str,
    category: str,
    project_id: int | None,
    trade_tags: list[str],
) -> list:
    """Split text into top-level sections and ingest each with auto-detected hazard tags.

    Calls ingest_document() per top-level section so each gets its own
    hazard tags based on content. The existing _split_into_sections() handles
    sub-section splitting within each chunk.
    """
    import re
    from backend.documents.ingestion import ingest_document

    # Split at top-level section headings (X.0 pattern)
    # Keep the heading with its content
    lines = full_text.split("\n")
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Match top-level section: X.0 TITLE (but not X.Y.Z subsections)
        if re.match(r"^\d+\.0\s+\S", stripped):
            if current_lines or current_heading:
                content = "\n".join(current_lines).strip()
                if content and len(content) > 50:
                    sections.append((current_heading, content))
            current_heading = stripped
            current_lines = []
        else:
            current_lines.append(line)

    # Last section
    if current_lines:
        content = "\n".join(current_lines).strip()
        if content and len(content) > 50:
            sections.append((current_heading, content))

    # Ingest each top-level section
    all_docs = []
    skipped = 0
    for heading, content in sections:
        hazard_tags = detect_hazard_tags(content)
        docs = ingest_document(
            db=db,
            project_id=project_id,
            title=title,
            raw_content=f"{heading}\n{content}" if heading else content,
            category=category,
            trade_tags=trade_tags,
            hazard_tags=hazard_tags,
        )
        all_docs.extend(docs)
        tag_str = ", ".join(hazard_tags[:3])
        if len(hazard_tags) > 3:
            tag_str += f" +{len(hazard_tags) - 3}"
        short_heading = heading[:50] if heading else "(preamble)"
        print(f"      {short_heading:50s}  {len(docs):2d} sections  [{tag_str}]")

    if skipped:
        print(f"    Skipped {skipped} short/empty sections")

    return all_docs


if __name__ == "__main__":
    main()
