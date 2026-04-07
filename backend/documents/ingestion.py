"""Document ingestion — upload, chunk, and tag safety documents.

Supports: site_safety_plan, company_procedure, osha_standard, trade_reference,
incident_report, lessons_learned, hazard_register, observation_insight.
"""

import json
import logging
import re

from sqlalchemy.orm import Session

from backend.models import SafetyDocument, utcnow

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "site_safety_plan",
    "company_procedure",
    "osha_standard",
    "trade_reference",
    "incident_report",
    "lessons_learned",
    "hazard_register",
    "observation_insight",
}


def _split_into_sections(raw_content: str) -> list[tuple[str, str]]:
    """Split document content into sections by headings.

    Returns list of (section_label, section_content) tuples.
    Handles markdown headings (##), numbered sections (1., 2.), and
    all-caps headings.
    """
    # Try markdown heading splits first
    md_pattern = r'^(#{1,4})\s+(.+)$'
    lines = raw_content.split('\n')

    sections: list[tuple[str, str]] = []
    current_label = ""
    current_lines: list[str] = []

    for line in lines:
        md_match = re.match(md_pattern, line.strip())
        # Match section headings like "1.0 Title" or "3.2.1 Title" — require
        # X.Y format to avoid splitting on numbered list items ("3. Use PPE")
        num_match = re.match(r'^(\d+\.\d+[\.\d]*\s+\S.*)$', line.strip())

        if md_match:
            # Save previous section
            if current_lines:
                content = '\n'.join(current_lines).strip()
                if content:
                    sections.append((current_label, content))
            current_label = md_match.group(2).strip()
            current_lines = []
        elif num_match and len(line.strip()) < 200:
            # Looks like a section heading (short numbered line)
            if current_lines:
                content = '\n'.join(current_lines).strip()
                if content:
                    sections.append((current_label, content))
            current_label = num_match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Don't forget the last section
    if current_lines:
        content = '\n'.join(current_lines).strip()
        if content:
            sections.append((current_label, content))

    # If no sections were found, return the whole thing as one section
    if not sections:
        sections = [("", raw_content.strip())]

    return sections


def _generate_attribution(title: str, section_label: str, category: str) -> str:
    """Generate a source attribution string for use in coaching responses."""
    category_labels = {
        "site_safety_plan": "Site Safety Plan",
        "company_procedure": "Company Procedure",
        "osha_standard": "OSHA Standard",
        "trade_reference": "Trade Reference",
        "incident_report": "Incident Report",
        "lessons_learned": "Lessons Learned",
        "hazard_register": "Project Hazard Register",
        "observation_insight": "Observation Insights",
    }
    cat_label = category_labels.get(category, category)

    if section_label:
        return f"{title} ({cat_label}), {section_label}"
    return f"{title} ({cat_label})"


def ingest_document(
    db: Session,
    project_id: int | None,
    title: str,
    raw_content: str,
    category: str,
    trade_tags: list[str] | None = None,
    hazard_tags: list[str] | None = None,
    language: str = "en",
) -> list[SafetyDocument]:
    """Upload and chunk a safety document into searchable sections.

    Args:
        db: Database session.
        project_id: Project this document belongs to (None for global/OSHA).
        title: Document name.
        raw_content: Full text content.
        category: One of the valid categories.
        trade_tags: List of relevant trade keys (e.g., ["ironworker", "carpenter"]).
        hazard_tags: List of hazard categories (e.g., ["fall_protection", "rigging"]).
        language: "en" or "es".

    Returns:
        List of SafetyDocument rows created.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {VALID_CATEGORIES}"
        )

    sections = _split_into_sections(raw_content)
    trade_tags_json = json.dumps(trade_tags or [])
    hazard_tags_json = json.dumps(hazard_tags or [])
    now = utcnow()

    documents: list[SafetyDocument] = []
    for section_label, section_content in sections:
        if not section_content.strip():
            continue
        # Skip very short sections — likely list items or fragment headings
        if len(section_content.strip()) < 80:
            logger.debug(
                "Skipping short section '%s' (%d chars)",
                (section_label or "untitled")[:50],
                len(section_content.strip()),
            )
            continue

        attribution = _generate_attribution(title, section_label, category)

        doc = SafetyDocument(
            project_id=project_id,
            title=title,
            content=section_content,
            category=category,
            section_label=section_label or None,
            trade_tags=trade_tags_json,
            hazard_tags=hazard_tags_json,
            source_attribution=attribution,
            language=language,
            created_at=now,
            updated_at=now,
        )
        db.add(doc)
        documents.append(doc)

    db.commit()
    for doc in documents:
        db.refresh(doc)

    logger.info(
        "Ingested document '%s' (%s) into %d sections for project_id=%s",
        title, category, len(documents), project_id,
    )
    return documents
