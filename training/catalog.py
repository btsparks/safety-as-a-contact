"""Photo cataloger — scan Sample Pics, parse filenames, populate photo_catalog.

Usage:
    python -m training.catalog [--pics-dir PATH] [--force]
"""

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from training.db import TrainingSession, init_training_db
from training.models import PhotoCatalog

DEFAULT_PICS_DIR = (
    Path.home()
    / "Desktop"
    / "AI Applications"
    / "Safety_as_a_Contact"
    / "Sample Pics"
)

# Pattern: {UUID}_{YYYYMMDD}000000_{UUID}-{hash}.jpg
_JPG_PATTERN = re.compile(
    r"^([A-Fa-f0-9-]+)_(\d{8})\d{6}_([A-Fa-f0-9-]+-[A-Fa-f0-9]+)\.(jpg|jpeg)$",
    re.IGNORECASE,
)

# PDF pattern: {UUID}_ObservationReport_${UUID}.pdf
_PDF_PATTERN = re.compile(
    r"^([A-Fa-f0-9-]+)_ObservationReport_.*\.pdf$",
    re.IGNORECASE,
)


def file_sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_filename(filename: str) -> dict | None:
    """Parse photo filename to extract date and identifiers.

    Returns dict with keys: date, is_pdf. Returns None if unrecognized.
    """
    m = _JPG_PATTERN.match(filename)
    if m:
        date_str = m.group(2)
        try:
            date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            date = None
        return {"date": date, "is_pdf": False}

    m = _PDF_PATTERN.match(filename)
    if m:
        return {"date": None, "is_pdf": True}

    return None


def catalog_directory(pics_dir: Path, force: bool = False) -> dict:
    """Scan a directory and create PhotoCatalog rows.

    Returns summary dict with counts.
    """
    init_training_db()
    db = TrainingSession()

    stats = {"new": 0, "skipped": 0, "unrecognized": 0, "pdfs": 0, "errors": 0}

    # Gather all image and PDF files
    files = sorted(pics_dir.iterdir())

    for fpath in files:
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in (".jpg", ".jpeg", ".pdf"):
            continue

        parsed = parse_filename(fpath.name)
        if parsed is None:
            stats["unrecognized"] += 1
            continue

        # Check if already cataloged
        file_path_str = str(fpath.resolve())
        if not force:
            existing = (
                db.query(PhotoCatalog)
                .filter(PhotoCatalog.file_path == file_path_str)
                .first()
            )
            if existing:
                stats["skipped"] += 1
                continue

        try:
            fhash = file_sha256(fpath)
            fsize = fpath.stat().st_size

            row = PhotoCatalog(
                file_path=file_path_str,
                file_name=fpath.name,
                file_hash=fhash,
                file_size_bytes=fsize,
                date_taken=parsed["date"],
                is_pdf=parsed["is_pdf"],
            )
            db.add(row)
            db.commit()

            if parsed["is_pdf"]:
                stats["pdfs"] += 1
            stats["new"] += 1

        except Exception as e:
            stats["errors"] += 1
            print(f"  Error cataloging {fpath.name}: {e}", file=sys.stderr)
            db.rollback()

    db.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Catalog construction site photos")
    parser.add_argument(
        "--pics-dir",
        type=Path,
        default=DEFAULT_PICS_DIR,
        help="Path to the photos directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-catalog even if file already exists in DB",
    )
    args = parser.parse_args()

    if not args.pics_dir.exists():
        print(f"Error: {args.pics_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {args.pics_dir}")
    stats = catalog_directory(args.pics_dir, force=args.force)

    print(f"\nCatalog complete:")
    print(f"  New photos:    {stats['new']}")
    print(f"  Already in DB: {stats['skipped']}")
    print(f"  PDFs flagged:  {stats['pdfs']}")
    print(f"  Unrecognized:  {stats['unrecognized']}")
    if stats["errors"]:
        print(f"  Errors:        {stats['errors']}")


if __name__ == "__main__":
    main()
