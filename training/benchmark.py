"""Benchmark the coaching engine against analyzed photos.

Usage:
    python -m training.benchmark [--run-label LABEL] [--trade TRADE] [--tier N]
                                 [--experience LEVEL] [--limit N] [--use-mock]
                                 [--notes "..."] [--delay SECONDS]
"""

import argparse
import json
import sys
import time

import anthropic

from backend.coaching.engine import _parse_coaching_response, coach_mock
from backend.coaching.prompts import build_system_prompt, build_user_message
from backend.coaching.trades import get_trade_profile
from backend.config import settings
from training.analyze import _load_and_resize
from training.db import TrainingSession, init_training_db
from training.models import (
    BenchmarkResult,
    BenchmarkRun,
    PhotoCatalog,
    PromptVersion,
    SceneAnalysis,
    utcnow,
)
from training.scoring import compute_auto_scores


def _benchmark_live(
    client: anthropic.Anthropic,
    photo_path: str,
    system_prompt: str,
    model: str,
) -> dict:
    """Run a single coaching call against a local photo via Claude API.

    Returns dict with response_text, response_mode, tokens, latency, etc.
    """
    image_data = _load_and_resize(photo_path)

    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_data,
            },
        },
        {"type": "text", "text": "(photo only)"},
    ]

    start = time.monotonic()
    resp = client.messages.create(
        model=model,
        max_tokens=300,
        temperature=0.3,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    latency = int((time.monotonic() - start) * 1000)

    raw_text = resp.content[0].text
    coaching_text, assessment = _parse_coaching_response(raw_text)

    # Truncate if needed
    if len(coaching_text) > 320:
        coaching_text = coaching_text[:317] + "..."

    return {
        "response_text": coaching_text,
        "response_mode": assessment.get("response_mode", "probe"),
        "hazard_category": assessment.get("hazard_category", ""),
        "severity": assessment.get("severity", 0),
        "prompt_tokens": resp.usage.input_tokens,
        "completion_tokens": resp.usage.output_tokens,
        "latency_ms": latency,
    }


def _benchmark_mock(observation_text: str) -> dict:
    """Run mock coaching for a photo (no API call)."""
    result = coach_mock(observation_text, media_urls=["local://photo.jpg"])
    return {
        "response_text": result.response_text,
        "response_mode": result.response_mode,
        "hazard_category": result.hazard_category,
        "severity": result.severity,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "latency_ms": result.latency_ms,
    }


def run_benchmark(
    run_label: str = "benchmark",
    trade: str | None = None,
    experience_level: str = "entry",
    worker_tier: int = 1,
    limit: int | None = None,
    use_mock: bool = False,
    notes: str = "",
    delay: float = 0.5,
    model: str = "claude-haiku-4-5-20251001",
    mentor_notes: str = "",
) -> dict:
    """Run a full benchmark pass. Returns summary stats."""
    init_training_db()
    db = TrainingSession()

    if not use_mock and not settings.anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY not set. Use --use-mock for mock mode.", file=sys.stderr)
        sys.exit(1)

    # Get analyzed photos
    query = (
        db.query(PhotoCatalog, SceneAnalysis)
        .join(SceneAnalysis, SceneAnalysis.photo_id == PhotoCatalog.id)
        .filter(PhotoCatalog.is_pdf == False)
        .order_by(PhotoCatalog.date_taken.asc())
    )
    if limit:
        query = query.limit(limit)

    rows = query.all()
    total = len(rows)

    if total == 0:
        print("No analyzed photos found. Run 'python -m training.analyze' first.")
        db.close()
        return {}

    # Build system prompt
    profile = get_trade_profile(trade)
    prompt_kwargs = dict(
        trade=trade or "general",
        trade_label=profile["label"],
        experience_level=experience_level,
        preferred_language="en",
        worker_tier=worker_tier,
        turn_number=1,
        thread_history="",
        has_photo=True,
        coaching_focus=profile["coaching_focus"],
        mentor_notes=mentor_notes,
    )
    system_prompt = build_system_prompt(**prompt_kwargs)

    # Save prompt version
    pv = PromptVersion(
        version_label=run_label,
        system_prompt_text=system_prompt,
        prompt_params=json.dumps(prompt_kwargs),
        notes=notes,
    )
    db.add(pv)
    db.commit()
    db.refresh(pv)

    # Create benchmark run
    run = BenchmarkRun(
        prompt_version_id=pv.id,
        run_label=run_label,
        model_used="mock" if use_mock else model,
        trade=trade,
        experience_level=experience_level,
        worker_tier=worker_tier,
        photo_count=total,
        notes=notes,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    client = None
    if not use_mock:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    print(f"Benchmark: '{run_label}' | {total} photos | {'mock' if use_mock else model}")
    print(f"  Tier {worker_tier} | {experience_level} | trade={trade or 'general'}")
    print()

    # Accumulators for summary
    score_totals = {
        "length": 0, "question": 0, "specific": 0,
        "prohibited": 0, "mode_match": 0, "mode_match_possible": 0,
    }
    mode_counts: dict[str, int] = {}

    for i, (photo, scene) in enumerate(rows, 1):
        try:
            if use_mock:
                result = _benchmark_mock(scene.scene_description or "(photo)")
            else:
                result = _benchmark_live(client, photo.file_path, system_prompt, model)

            # Auto-score
            scores = compute_auto_scores(
                result["response_text"],
                result["response_mode"],
                scene.recommended_mode,
            )

            # Save result
            br = BenchmarkResult(
                run_id=run.id,
                photo_id=photo.id,
                scene_analysis_id=scene.id,
                response_text=result["response_text"],
                response_mode=result["response_mode"],
                hazard_category=result["hazard_category"],
                severity=result["severity"],
                prompt_tokens=result["prompt_tokens"],
                completion_tokens=result["completion_tokens"],
                latency_ms=result["latency_ms"],
                score_length_ok=scores["score_length_ok"],
                score_has_question=scores["score_has_question"],
                score_is_specific=scores["score_is_specific"],
                score_no_prohibited=scores["score_no_prohibited"],
                score_mode_match=scores["score_mode_match"],
                auto_score_total=scores["auto_score_total"],
            )
            db.add(br)
            run.completed_count = i
            db.commit()

            # Accumulate stats
            score_totals["length"] += int(scores["score_length_ok"])
            score_totals["question"] += int(scores["score_has_question"])
            score_totals["specific"] += int(scores["score_is_specific"])
            score_totals["prohibited"] += int(scores["score_no_prohibited"])
            if scores["score_mode_match"] is not None:
                score_totals["mode_match"] += int(scores["score_mode_match"])
                score_totals["mode_match_possible"] += 1

            mode = result["response_mode"]
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

            # Progress
            score_str = f"{scores['auto_score_total']}/{scores['max_possible']}"
            preview = result["response_text"][:60].replace("\n", " ")
            print(f"  [{i}/{total}] {mode:8s} ({score_str}) \"{preview}...\"")

        except Exception as e:
            print(f"  [{i}/{total}] ERROR: {e}", file=sys.stderr)
            db.rollback()

        if not use_mock and i < total:
            time.sleep(delay)

    run.finished_at = utcnow()
    db.commit()
    db.close()

    # Print summary
    print(f"\n{'='*60}")
    print(f"Run: \"{run_label}\" | {total} photos | Run ID: {run.id}")
    print(f"{'='*60}")
    print(f"Auto-scores:")
    print(f"  Length OK:      {score_totals['length']}/{total} ({100*score_totals['length']/total:.1f}%)")
    print(f"  Has question:   {score_totals['question']}/{total} ({100*score_totals['question']/total:.1f}%)")
    print(f"  Is specific:    {score_totals['specific']}/{total} ({100*score_totals['specific']/total:.1f}%)")
    print(f"  No prohibited:  {score_totals['prohibited']}/{total} ({100*score_totals['prohibited']/total:.1f}%)")
    if score_totals["mode_match_possible"]:
        mm = score_totals["mode_match"]
        mmp = score_totals["mode_match_possible"]
        print(f"  Mode match:     {mm}/{mmp} ({100*mm/mmp:.1f}%)")
    print(f"\nMode distribution:")
    for mode in sorted(mode_counts, key=mode_counts.get, reverse=True):
        print(f"  {mode:8s}: {mode_counts[mode]}")

    return {"run_id": run.id, "total": total, "scores": score_totals, "modes": mode_counts}


def main():
    parser = argparse.ArgumentParser(description="Benchmark coaching engine")
    parser.add_argument("--run-label", default="benchmark", help="Label for this run")
    parser.add_argument("--trade", default=None, help="Worker trade for coaching context")
    parser.add_argument("--tier", type=int, default=1, help="Worker tier (1-4)")
    parser.add_argument("--experience", default="entry", help="Experience level")
    parser.add_argument("--limit", type=int, default=None, help="Max photos to benchmark")
    parser.add_argument("--use-mock", action="store_true", help="Use mock engine (no API)")
    parser.add_argument("--notes", default="", help="Notes about this run")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="Model for coaching")
    args = parser.parse_args()

    run_benchmark(
        run_label=args.run_label,
        trade=args.trade,
        experience_level=args.experience,
        worker_tier=args.tier,
        limit=args.limit,
        use_mock=args.use_mock,
        notes=args.notes,
        delay=args.delay,
        model=args.model,
    )


if __name__ == "__main__":
    main()
