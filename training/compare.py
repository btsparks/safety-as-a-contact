"""Compare two benchmark runs side by side.

Usage:
    python -m training.compare RUN_A RUN_B [--detail] [--worst N]
"""

import argparse
import sys

from training.db import TrainingSession, init_training_db
from training.models import BenchmarkResult, BenchmarkRun, PhotoCatalog, SceneAnalysis


def compare_runs(run_a_id: int, run_b_id: int, detail: bool = False, worst: int = 0):
    """Compare two benchmark runs."""
    init_training_db()
    db = TrainingSession()

    run_a = db.get(BenchmarkRun,run_a_id)
    run_b = db.get(BenchmarkRun,run_b_id)

    if not run_a or not run_b:
        print("Error: One or both run IDs not found.", file=sys.stderr)
        db.close()
        return

    # Get results keyed by photo_id
    results_a = {
        r.photo_id: r
        for r in db.query(BenchmarkResult).filter(BenchmarkResult.run_id == run_a_id).all()
    }
    results_b = {
        r.photo_id: r
        for r in db.query(BenchmarkResult).filter(BenchmarkResult.run_id == run_b_id).all()
    }

    # Shared photos
    shared_ids = set(results_a.keys()) & set(results_b.keys())
    n = len(shared_ids)

    if n == 0:
        print("No shared photos between these runs.")
        db.close()
        return

    # Compute aggregates
    def _agg(results: dict, ids: set) -> dict:
        items = [results[pid] for pid in ids]
        total = len(items)
        length = sum(1 for r in items if r.score_length_ok) / total * 100
        question = sum(1 for r in items if r.score_has_question) / total * 100
        specific = sum(1 for r in items if r.score_is_specific) / total * 100
        prohibited = sum(1 for r in items if r.score_no_prohibited) / total * 100

        mode_items = [r for r in items if r.score_mode_match is not None]
        mode_match = (sum(1 for r in mode_items if r.score_mode_match) / len(mode_items) * 100) if mode_items else None

        avg_auto = sum(r.auto_score_total for r in items) / total

        rated = [r for r in items if r.human_rating is not None]
        avg_human = sum(r.human_rating for r in rated) / len(rated) if rated else None

        avg_latency = sum(r.latency_ms for r in items) / total
        avg_prompt_tokens = sum(r.prompt_tokens for r in items) / total
        avg_completion_tokens = sum(r.completion_tokens for r in items) / total

        modes: dict[str, int] = {}
        for r in items:
            modes[r.response_mode] = modes.get(r.response_mode, 0) + 1

        return {
            "length": length, "question": question, "specific": specific,
            "prohibited": prohibited, "mode_match": mode_match,
            "avg_auto": avg_auto, "avg_human": avg_human,
            "avg_latency": avg_latency, "avg_prompt_tokens": avg_prompt_tokens,
            "avg_completion_tokens": avg_completion_tokens,
            "modes": modes, "human_count": len(rated),
        }

    a = _agg(results_a, shared_ids)
    b = _agg(results_b, shared_ids)

    def _delta(va, vb):
        if va is None or vb is None:
            return "    -"
        d = vb - va
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:.1f}"

    def _fmt(v, fmt=".1f"):
        return f"{v:{fmt}}" if v is not None else "    -"

    # Print comparison
    label_a = f"\"{run_a.run_label}\" (#{run_a_id})"
    label_b = f"\"{run_b.run_label}\" (#{run_b_id})"

    print(f"\nComparing: {label_a} vs {label_b}")
    print(f"Shared photos: {n}")
    print()
    print(f"{'':24s} {'Run A':>10s} {'Run B':>10s} {'Delta':>10s}")
    print("-" * 56)
    print(f"{'Length OK':24s} {a['length']:>9.1f}% {b['length']:>9.1f}% {_delta(a['length'], b['length']):>10s}%")
    print(f"{'Has question':24s} {a['question']:>9.1f}% {b['question']:>9.1f}% {_delta(a['question'], b['question']):>10s}%")
    print(f"{'Is specific':24s} {a['specific']:>9.1f}% {b['specific']:>9.1f}% {_delta(a['specific'], b['specific']):>10s}%")
    print(f"{'No prohibited':24s} {a['prohibited']:>9.1f}% {b['prohibited']:>9.1f}% {_delta(a['prohibited'], b['prohibited']):>10s}%")

    if a["mode_match"] is not None or b["mode_match"] is not None:
        mm_a = _fmt(a["mode_match"])
        mm_b = _fmt(b["mode_match"])
        print(f"{'Mode match':24s} {mm_a:>9s}% {mm_b:>9s}% {_delta(a['mode_match'], b['mode_match']):>10s}%")

    print(f"{'Avg auto-score':24s} {a['avg_auto']:>10.1f} {b['avg_auto']:>10.1f} {_delta(a['avg_auto'], b['avg_auto']):>10s}")

    if a["avg_human"] is not None or b["avg_human"] is not None:
        hum_a = _fmt(a["avg_human"])
        hum_b = _fmt(b["avg_human"])
        print(f"{'Avg human rating':24s} {hum_a:>10s} {hum_b:>10s} {_delta(a['avg_human'], b['avg_human']):>10s}")

    print()
    print(f"{'Avg latency (ms)':24s} {a['avg_latency']:>10.0f} {b['avg_latency']:>10.0f} {_delta(a['avg_latency'], b['avg_latency']):>10s}")
    print(f"{'Avg prompt tokens':24s} {a['avg_prompt_tokens']:>10.0f} {b['avg_prompt_tokens']:>10.0f} {_delta(a['avg_prompt_tokens'], b['avg_prompt_tokens']):>10s}")
    print(f"{'Avg completion tokens':24s} {a['avg_completion_tokens']:>10.0f} {b['avg_completion_tokens']:>10.0f} {_delta(a['avg_completion_tokens'], b['avg_completion_tokens']):>10s}")

    # Mode distribution
    all_modes = sorted(set(list(a["modes"].keys()) + list(b["modes"].keys())))
    if all_modes:
        print(f"\nMode distribution:")
        for mode in all_modes:
            ca = a["modes"].get(mode, 0)
            cb = b["modes"].get(mode, 0)
            d = cb - ca
            sign = "+" if d >= 0 else ""
            print(f"  {mode:12s} {ca:>6d} {cb:>6d}    {sign}{d}")

    # Show worst results from run B
    if worst > 0:
        print(f"\nWorst {worst} results in Run B:")
        print("-" * 56)
        worst_results = sorted(
            [results_b[pid] for pid in shared_ids],
            key=lambda r: r.auto_score_total,
        )[:worst]
        for r in worst_results:
            photo = db.get(PhotoCatalog,r.photo_id)
            print(f"  [{r.auto_score_total}/5] {r.response_mode:8s} | {photo.file_name[:40]}...")
            print(f"    \"{r.response_text[:80]}...\"")

    # Detail: show photos where scores diverged
    if detail:
        print(f"\nPhotos where auto-score changed:")
        print("-" * 56)
        for pid in sorted(shared_ids):
            ra = results_a[pid]
            rb = results_b[pid]
            if ra.auto_score_total != rb.auto_score_total:
                photo = db.get(PhotoCatalog,pid)
                d = rb.auto_score_total - ra.auto_score_total
                sign = "+" if d >= 0 else ""
                print(
                    f"  {sign}{d}: {ra.auto_score_total}->{rb.auto_score_total} "
                    f"| {photo.file_name[:40]}..."
                )

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Compare two benchmark runs")
    parser.add_argument("run_a", type=int, help="First run ID")
    parser.add_argument("run_b", type=int, help="Second run ID")
    parser.add_argument("--detail", action="store_true", help="Show per-photo diffs")
    parser.add_argument("--worst", type=int, default=0, help="Show N worst results from run B")
    args = parser.parse_args()

    compare_runs(args.run_a, args.run_b, detail=args.detail, worst=args.worst)


if __name__ == "__main__":
    main()
