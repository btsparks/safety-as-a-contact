"""PDF text extraction utility for safety documents.

Extracts clean text from safety document PDFs, strips repeated
headers/footers, normalizes section numbering, and produces output
compatible with the existing _split_into_sections() ingestion function.

Requires: PyMuPDF (pip install PyMuPDF)
"""

import logging
import re

logger = logging.getLogger(__name__)


def extract_pdf_text(
    pdf_path: str,
    skip_pages: list[int] | None = None,
    header_pattern: str | None = None,
    footer_pattern: str | None = None,
) -> str:
    """Extract and clean text from a safety document PDF.

    Args:
        pdf_path: Path to the PDF file.
        skip_pages: 1-based page numbers to skip (e.g., [1, 2, 3, 4] for
            cover page and table of contents).
        header_pattern: Regex pattern to identify repeated header lines.
            Applied line-by-line; matching lines are removed.
        footer_pattern: Regex pattern to identify repeated footer lines.
            Applied line-by-line; matching lines are removed.

    Returns:
        Cleaned text with section structure preserved, ready for
        _split_into_sections() in ingestion.py.
    """
    import fitz  # PyMuPDF

    skip_set = set(skip_pages or [])
    doc = fitz.open(pdf_path)
    page_texts: list[str] = []

    for page_num in range(len(doc)):
        # skip_pages is 1-based
        if (page_num + 1) in skip_set:
            continue

        raw = doc[page_num].get_text()
        lines = raw.split("\n")
        cleaned_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Skip empty lines (will normalize whitespace later)
            if not stripped:
                cleaned_lines.append("")
                continue

            # Strip standalone page numbers (e.g., "10" on its own line)
            if re.match(r"^\d{1,3}\s*$", stripped):
                continue

            # Strip lines matching header pattern
            if header_pattern and re.search(header_pattern, stripped, re.IGNORECASE):
                continue

            # Strip lines matching footer pattern
            if footer_pattern and re.search(footer_pattern, stripped, re.IGNORECASE):
                continue

            cleaned_lines.append(stripped)

        page_text = "\n".join(cleaned_lines)
        if page_text.strip():
            page_texts.append(page_text)

    doc.close()

    full_text = "\n\n".join(page_texts)

    # Post-processing
    full_text = _join_split_section_numbers(full_text)
    full_text = _normalize_bullets(full_text)
    full_text = _collapse_whitespace(full_text)

    return full_text.strip()


def _join_split_section_numbers(text: str) -> str:
    """Join section numbers that appear on their own line with the next line.

    Many PDF extractors split "1.0\\nGeneral Requirements" into two lines.
    This joins them into "1.0 General Requirements" so _split_into_sections()
    can detect the heading correctly.

    Only joins when the number line matches X.Y or X.Y.Z pattern (not bare
    integers like "1" or "2" which could be list items).
    """
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # Match section number patterns: 1.0, 1.1, 1.1.1, 3.11.17, etc.
        if re.match(r"^\d+\.\d+[\.\d]*\s*$", stripped):
            # Look ahead for a non-empty title line
            if i + 1 < len(lines) and lines[i + 1].strip():
                next_line = lines[i + 1].strip()
                # Only join if next line looks like a heading (starts with letter,
                # short enough to be a title, not ending in period which
                # indicates a sentence rather than a heading)
                if (
                    re.match(r"^[A-Za-z]", next_line)
                    and len(next_line) < 80
                    and not next_line.rstrip().endswith(".")
                ):
                    result.append(f"{stripped} {next_line}")
                    i += 2
                    continue
        result.append(lines[i])
        i += 1
    return "\n".join(result)


def _normalize_bullets(text: str) -> str:
    """Replace common bullet characters with '- ' for consistency."""
    # Replace bullet chars at start of line
    text = re.sub(r"^[•●◦▪■□►]\s*", "- ", text, flags=re.MULTILINE)
    # Also handle the case where PDF extracts bullet as standalone char line
    # followed by content on the next line
    text = re.sub(r"^[•●◦▪■□►]\s*\n", "- ", text, flags=re.MULTILINE)
    # Handle Unicode bullet (U+2022) that shows as "�" on some systems
    text = re.sub(r"^�\s*", "- ", text, flags=re.MULTILINE)
    return text


def _collapse_whitespace(text: str) -> str:
    """Collapse 3+ consecutive blank lines into 2."""
    return re.sub(r"\n{4,}", "\n\n\n", text)


# ── Pre-built header patterns for known documents ────────────────────────

WOLLAM_HEADER_PATTERN = (
    r"WOLLAM CONSTRUCTION, LLC"
    r"|^Doc No:\s*$"
    r"|^SHMS$"
    r"|^Initial Issue Date$"
    r"|^\d{1,2}/\d{1,2}/\d{4,5}$"
    r"|^Revision Date:"
    r"|^SAFETY & HEALTH MANAGEMENT SYSTEM$"
    r"|^Revision No\.$"
    r"|^1\.4$"
    r"|^Next Review Date:"
    r"|^Preparation:\s+"
    r"|^Authority:\s+"
    r"|^Issuing Dept:\s+"
    r"|^Page:\s*$"
    r"|^Page \d+ of \d+"
    r"|Uncontrolled copy if printed"
    r"|^Printed on:"
    r"|© WOLLAM CONSTRUCTION"
    r"|^WOLLAM CONSTRUCTION$"
    r"|\.{5,}"
    r"|ERROR! BOOKMARK NOT DEFINED"
)

# Valar SSSP has minimal headers — just standalone page numbers,
# which are handled generically by the page number stripping logic.
VALAR_HEADER_PATTERN = None
