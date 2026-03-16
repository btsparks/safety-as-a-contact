"""Human review CLI — rate coaching responses 1-5.

Usage:
    python -m training.review [--run-id ID] [--unreviewed-only] [--open-photo]
"""

import argparse
import json
import os
import sys

from training.db import TrainingSession, init_training_db
from training.models import (
    BenchmarkResult,
    BenchmarkRun,
    PhotoCatalog,
    SceneAnalysis,
    utcnow,
)


def _format_scores(result: BenchmarkResult) -> str:
    """Format auto-scores as a visual line."""
    checks = [
        ("length", result.score_length_ok),
        ("question", result.score_has_question),
        ("specific", result.score_is_specific),
        ("no-prohibited", result.score_no_prohibited),
        ("mode-match", result.score_mode_match),
    ]
    parts = []
    for label, val in checks:
        if val is None:
            parts.append(f"[--] {label}")
        elif val:
            parts.append(f"[OK] {label}")
        else:
            parts.append(f"[XX] {label}")
    return "  ".join(parts)


def review_run(run_id: int, unreviewed_only: bool = True, open_photo: bool = False):
    """Interactive review loop for a benchmark run."""
    init_training_db()
    db = TrainingSession()

    run = db.get(BenchmarkRun,run_id)
    if not run:
        print(f"Error: Run ID {run_id} not found.", file=sys.stderr)
        db.close()
        return

    query = (
        db.query(BenchmarkResult, PhotoCatalog, SceneAnalysis)
        .join(PhotoCatalog, BenchmarkResult.photo_id == PhotoCatalog.id)
        .outerjoin(SceneAnalysis, BenchmarkResult.scene_analysis_id == SceneAnalysis.id)
        .filter(BenchmarkResult.run_id == run_id)
    )
    if unreviewed_only:
        query = query.filter(BenchmarkResult.human_rating.is_(None))

    query = query.order_by(BenchmarkResult.id)
    items = query.all()
    total = len(items)

    if total == 0:
        print("Nothing to review (all rated or no results).")
        db.close()
        return

    print(f"\nReviewing run: \"{run.run_label}\" (ID {run.id})")
    print(f"Photos to review: {total}\n")

    reviewed = 0
    ratings = []

    for i, (result, photo, scene) in enumerate(items, 1):
        sep = "=" * 60
        thin = "-" * 60

        print(sep)
        date_str = photo.date_taken.strftime("%m/%d/%Y") if photo.date_taken else "unknown"
        print(f"Photo [{i}/{total}]: {photo.project_name or 'Unknown'} - {date_str}")
        print(f"File: {photo.file_name}")
        print(thin)

        if scene:
            print(f"Scene: {scene.scene_description}")
            try:
                hazards = json.loads(scene.hazards_found or "[]")
                if hazards:
                    for h in hazards:
                        print(f"  Hazard: [{h.get('category', '?')}] {h.get('hazard', '?')} (sev {h.get('severity', '?')})")
                else:
                    print("  Hazards: none identified")
            except json.JSONDecodeError:
                print(f"  Hazards: {scene.hazards_found}")
            print(f"  Recommended mode: {scene.recommended_mode}")
        else:
            print("  (no scene analysis)")

        print(thin)
        print(f"Coaching response ({result.response_mode}):")
        print(f"  \"{result.response_text}\"")
        print(thin)
        print(f"Auto-scores: {_format_scores(result)}")
        print(f"Total: {result.auto_score_total}")
        print(thin)

        # Open photo if requested
        if open_photo:
            try:
                os.startfile(photo.file_path)
            except Exception:
                pass

        # Prompt for rating
        while True:
            choice = input("Rate 1-5 (s=skip, q=quit, n=add notes): ").strip().lower()

            if choice == "q":
                print(f"\nQuitting. Reviewed {reviewed} photos.")
                if ratings:
                    avg = sum(ratings) / len(ratings)
                    print(f"Average rating: {avg:.1f}")
                db.close()
                return

            if choice == "s":
                print()
                break

            if choice == "n":
                note = input("  Notes: ").strip()
                result.human_notes = note
                db.commit()
                print("  Notes saved.")
                continue

            try:
                rating = int(choice)
                if 1 <= rating <= 5:
                    result.human_rating = rating
                    result.reviewed_at = utcnow()
                    db.commit()
                    reviewed += 1
                    ratings.append(rating)
                    print(f"  Rated {rating}/5\n")
                    break
                else:
                    print("  Enter 1-5, s, q, or n")
            except ValueError:
                print("  Enter 1-5, s, q, or n")

    print(f"\nReview complete. Rated {reviewed}/{total} photos.")
    if ratings:
        avg = sum(ratings) / len(ratings)
        print(f"Average rating: {avg:.1f}")

    db.close()


def list_runs():
    """List all benchmark runs."""
    init_training_db()
    db = TrainingSession()
    runs = db.query(BenchmarkRun).order_by(BenchmarkRun.id.desc()).all()

    if not runs:
        print("No benchmark runs found.")
        db.close()
        return

    print(f"{'ID':>4}  {'Label':<30}  {'Photos':>6}  {'Reviewed':>8}  {'Avg Rating':>10}")
    print("-" * 70)

    for run in runs:
        reviewed = (
            db.query(BenchmarkResult)
            .filter(
                BenchmarkResult.run_id == run.id,
                BenchmarkResult.human_rating.isnot(None),
            )
            .count()
        )
        avg_q = (
            db.query(BenchmarkResult.human_rating)
            .filter(
                BenchmarkResult.run_id == run.id,
                BenchmarkResult.human_rating.isnot(None),
            )
            .all()
        )
        avg = sum(r[0] for r in avg_q) / len(avg_q) if avg_q else 0

        avg_str = f"{avg:.1f}" if avg_q else "-"
        print(
            f"{run.id:>4}  {(run.run_label or '')[:30]:<30}  "
            f"{run.photo_count:>6}  {reviewed:>8}  {avg_str:>10}"
        )

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Review coaching responses")
    parser.add_argument("--run-id", type=int, help="Benchmark run ID to review")
    parser.add_argument("--all", action="store_true", help="Include already-reviewed")
    parser.add_argument("--open-photo", action="store_true", help="Open photo in viewer")
    parser.add_argument("--list-runs", action="store_true", help="List all benchmark runs")
    args = parser.parse_args()

    if args.list_runs:
        list_runs()
        return

    if not args.run_id:
        print("Listing runs (use --run-id N to review):\n")
        list_runs()
        return

    review_run(
        run_id=args.run_id,
        unreviewed_only=not args.all,
        open_photo=args.open_photo,
    )


if __name__ == "__main__":
    main()
