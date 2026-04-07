"""Report generation — JSON + human-readable terminal output.

Produces both a structured JSON report file and a formatted terminal summary
that makes it immediately clear what passed, what failed, and why.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from training.quality_gate import QualityGateReport


def _status_icon(status: str) -> str:
    """Map status to terminal icon."""
    return {
        "PASS": "PASS",
        "FAIL": "FAIL",
        "WARN": "WARN",
        "UNKNOWN": "----",
    }.get(status, "????")


def format_terminal_report(report: QualityGateReport, prompt_version: str = "") -> str:
    """Format a Quality Gate report for terminal display."""
    lines = []

    # Header
    header = f"QUALITY GATE REPORT"
    if prompt_version:
        header += f" -- Prompt {prompt_version}"
    lines.append(f"{'=' * 60}")
    lines.append(f"  {header}")
    lines.append(f"{'=' * 60}")

    if report.persona_name:
        lines.append(f"Persona: {report.persona_name}  |  "
                     f"{report.total_sessions} sessions  |  "
                     f"{report.total_responses_evaluated} responses  |  "
                     f"{report.elapsed_seconds:.0f}s")
    lines.append("")

    # Categories
    for cat in report.categories:
        # Category header
        icon = _status_icon(cat.status)
        padding = 48 - len(cat.name)
        dots = "." * max(padding, 2)
        lines.append(f"  {cat.name} {dots} {icon}")

        # Details
        if cat.details:
            detail_parts = []
            for k, v in cat.details.items():
                if isinstance(v, float):
                    if "rate" in k or "ratio" in k:
                        detail_parts.append(f"{k}: {v}%")
                    else:
                        detail_parts.append(f"{k}: {v}")
                else:
                    detail_parts.append(f"{k}: {v}")

            # Show up to 4 details per line
            for i in range(0, len(detail_parts), 4):
                chunk = detail_parts[i:i + 4]
                lines.append(f"    {' | '.join(chunk)}")

        # Threshold failures
        if cat.threshold_failures:
            for fail in cat.threshold_failures:
                lines.append(f"    >> {fail}")

        # Diagnosis
        if cat.diagnosis and cat.status != "PASS":
            lines.append(f"    -> {cat.diagnosis}")

        lines.append("")

    # Overall
    lines.append(f"{'=' * 60}")
    overall_icon = _status_icon(report.overall_status)
    lines.append(f"  OVERALL: {report.overall_status} [{overall_icon}]")
    if report.overall_diagnosis:
        lines.append(f"  {report.overall_diagnosis}")
    lines.append(f"{'=' * 60}")

    return "\n".join(lines)


def save_json_report(
    report: QualityGateReport,
    output_dir: str | Path = "training_reports",
    prompt_version: str = "",
) -> Path:
    """Save the quality gate report as a JSON file. Returns the file path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    persona = report.persona_name.lower() if report.persona_name else "unknown"
    version = prompt_version.replace(" ", "_") if prompt_version else "current"
    filename = f"qg_{persona}_{version}_{timestamp}.json"

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        **report.to_dict(),
    }

    filepath = output_dir / filename
    filepath.write_text(json.dumps(data, indent=2))
    return filepath


def format_comparison_report(
    report_a: QualityGateReport,
    report_b: QualityGateReport,
    label_a: str = "A",
    label_b: str = "B",
) -> str:
    """Format a side-by-side comparison of two quality gate reports."""
    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"  COMPARISON: {label_a} vs {label_b}")
    lines.append(f"{'=' * 60}")
    lines.append("")

    # Compare each category
    cats_a = {c.name: c for c in report_a.categories}
    cats_b = {c.name: c for c in report_b.categories}

    all_cats = list(dict.fromkeys(list(cats_a.keys()) + list(cats_b.keys())))

    for cat_name in all_cats:
        ca = cats_a.get(cat_name)
        cb = cats_b.get(cat_name)

        status_a = ca.status if ca else "N/A"
        status_b = cb.status if cb else "N/A"

        lines.append(f"  {cat_name}:")
        lines.append(f"    {label_a}: {status_a}  |  {label_b}: {status_b}")

        # Compare shared detail keys
        if ca and cb:
            all_keys = list(dict.fromkeys(list(ca.details.keys()) + list(cb.details.keys())))
            for key in all_keys:
                val_a = ca.details.get(key)
                val_b = cb.details.get(key)
                if val_a is not None and val_b is not None:
                    diff = val_b - val_a
                    direction = "+" if diff > 0 else ""
                    lines.append(f"      {key}: {val_a} -> {val_b} ({direction}{diff:.1f})")

        lines.append("")

    # Overall
    lines.append(f"  OVERALL: {label_a}={report_a.overall_status} | {label_b}={report_b.overall_status}")
    lines.append(f"{'=' * 60}")

    return "\n".join(lines)
