"""Observation insight generation — aggregates worker observations into
document-layer insight reports that surface back to workers.

These are NOT AI-generated opinions. They are statistical summaries of real
observation data. The authority is the collective input of the workforce.

Usage:
    python -m backend.documents.insights --period weekly --project-id 1
    python -m backend.documents.insights --period monthly --company-id 1 --scope company
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    Company,
    Observation,
    Project,
    SafetyDocument,
    utcnow,
)

logger = logging.getLogger(__name__)


def _period_start(period: str) -> datetime:
    """Calculate the start timestamp for a given period."""
    now = utcnow()
    if period == "daily":
        return now - timedelta(days=1)
    elif period == "weekly":
        return now - timedelta(weeks=1)
    elif period == "monthly":
        return now - timedelta(days=30)
    elif period == "quarterly":
        return now - timedelta(days=90)
    else:
        return now - timedelta(weeks=1)


def _format_count_insight(count: int, category: str, scope_label: str, period: str) -> str:
    """Format a single count-based insight."""
    period_label = {"daily": "today", "weekly": "this week", "monthly": "this month", "quarterly": "this quarter"}
    time_label = period_label.get(period, "recently")
    return f"{count} {category.replace('_', ' ')} observations on {scope_label} {time_label}."


def generate_project_insights(
    db: Session,
    project_id: int,
    period: str = "weekly",
) -> list[SafetyDocument]:
    """Generate observation insights for a specific project.

    Creates SafetyDocument entries with category='observation_insight' that
    can be surfaced back to workers via document retrieval.

    Returns list of created insight documents.
    """
    project = db.get(Project, project_id)
    if not project:
        logger.warning("Project %d not found, skipping insight generation", project_id)
        return []

    start = _period_start(period)

    # Count observations by hazard category for this project
    cat_counts = (
        db.query(Observation.hazard_category, func.count(Observation.id))
        .filter(
            Observation.project_id == project_id,
            Observation.created_at >= start,
            Observation.hazard_category.isnot(None),
        )
        .group_by(Observation.hazard_category)
        .all()
    )

    if not cat_counts:
        logger.info("No observations for project %d in period %s", project_id, period)
        return []

    total_obs = sum(count for _, count in cat_counts)

    # Build insight content
    insight_lines = [
        f"Observation Insights for {project.name} ({period})",
        f"Total observations: {total_obs}",
        "",
    ]
    for category, count in sorted(cat_counts, key=lambda x: -x[1]):
        insight_lines.append(f"- {category.replace('_', ' ').title()}: {count} observations")

    # Top category highlight
    top_cat, top_count = max(cat_counts, key=lambda x: x[1])
    insight_lines.append("")
    insight_lines.append(
        f"Most reported: {top_cat.replace('_', ' ')} ({top_count} of {total_obs} total)."
    )

    content = "\n".join(insight_lines)

    # Build hazard tags from observed categories
    hazard_tags = [cat for cat, _ in cat_counts]

    now = utcnow()

    # Remove old insights for this project and period
    old_insights = (
        db.query(SafetyDocument)
        .filter(
            SafetyDocument.project_id == project_id,
            SafetyDocument.category == "observation_insight",
            SafetyDocument.section_label == f"{period}_summary",
        )
        .all()
    )
    for old in old_insights:
        db.delete(old)

    doc = SafetyDocument(
        project_id=project_id,
        title=f"{project.name} — Observation Insights ({period.title()})",
        content=content,
        category="observation_insight",
        section_label=f"{period}_summary",
        trade_tags=json.dumps(["all"]),
        hazard_tags=json.dumps(hazard_tags),
        source_attribution=f"Observation Insights, {project.name}",
        language="en",
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    logger.info(
        "Generated %s insights for project '%s': %d observations, %d categories",
        period, project.name, total_obs, len(cat_counts),
    )
    return [doc]


def generate_company_insights(
    db: Session,
    company_id: int,
    period: str = "monthly",
) -> list[SafetyDocument]:
    """Generate company-wide cross-project observation insights.

    Only created when safety director enables cross-project sharing.
    """
    company = db.get(Company, company_id)
    if not company:
        logger.warning("Company %d not found", company_id)
        return []

    start = _period_start(period)

    # Get all project IDs for this company
    project_ids = [
        p.id for p in
        db.query(Project).filter(Project.company_id == company_id).all()
    ]
    if not project_ids:
        return []

    # Count observations across all company projects
    cat_counts = (
        db.query(Observation.hazard_category, func.count(Observation.id))
        .filter(
            Observation.project_id.in_(project_ids),
            Observation.created_at >= start,
            Observation.hazard_category.isnot(None),
        )
        .group_by(Observation.hazard_category)
        .all()
    )

    if not cat_counts:
        return []

    total_obs = sum(count for _, count in cat_counts)

    # Count how many projects have observations
    projects_with_obs = (
        db.query(func.count(func.distinct(Observation.project_id)))
        .filter(
            Observation.project_id.in_(project_ids),
            Observation.created_at >= start,
        )
        .scalar()
    )

    insight_lines = [
        f"Company-Wide Observation Insights ({period})",
        f"Total observations across {projects_with_obs} projects: {total_obs}",
        "",
    ]
    for category, count in sorted(cat_counts, key=lambda x: -x[1]):
        insight_lines.append(f"- {category.replace('_', ' ').title()}: {count} observations")

    content = "\n".join(insight_lines)
    hazard_tags = [cat for cat, _ in cat_counts]

    now = utcnow()

    # Remove old company-wide insights
    old_insights = (
        db.query(SafetyDocument)
        .filter(
            SafetyDocument.project_id.is_(None),
            SafetyDocument.category == "observation_insight",
            SafetyDocument.section_label == f"company_{company_id}_{period}_summary",
        )
        .all()
    )
    for old in old_insights:
        db.delete(old)

    doc = SafetyDocument(
        project_id=None,  # Company-wide, not project-specific
        title=f"{company.name} — Company Observation Insights ({period.title()})",
        content=content,
        category="observation_insight",
        section_label=f"company_{company_id}_{period}_summary",
        trade_tags=json.dumps(["all"]),
        hazard_tags=json.dumps(hazard_tags),
        source_attribution=f"Company Observation Insights, {company.name}",
        language="en",
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    logger.info(
        "Generated %s company insights for '%s': %d observations across %d projects",
        period, company.name, total_obs, projects_with_obs,
    )
    return [doc]
