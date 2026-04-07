"""CLI entry point for the headless evaluation pipeline.

Usage:
    python -m training evaluate miguel --sessions 10 --turns 4
    python -m training simulate jake --sessions 5
    python -m training gate --sessions 10
    python -m training report --latest
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("training.cli")


def _get_db():
    """Get a main database session."""
    from backend.database import SessionLocal
    return SessionLocal()


def _init_dbs():
    """Initialize both main and training databases."""
    from backend.database import init_db
    from training.db import init_training_db
    init_db()
    init_training_db()


def _snapshot_prompt_version(label: str) -> int | None:
    """Snapshot the current prompt and store in PromptVersion table."""
    from backend.coaching.prompts import build_system_prompt
    from training.db import TrainingSession, init_training_db
    from training.models import PromptVersion

    init_training_db()
    prompt_text = build_system_prompt(
        trade="general construction",
        trade_label="General Construction",
        experience_level="entry",
        worker_tier=1,
        turn_number=1,
    )

    tdb = TrainingSession()
    pv = PromptVersion(
        version_label=label,
        system_prompt_text=prompt_text,
        prompt_params=json.dumps({"trade": "general", "tier": 1, "turn": 1}),
    )
    tdb.add(pv)
    tdb.commit()
    tdb.refresh(pv)
    version_id = pv.id
    tdb.close()
    return version_id


def _run_simulation(persona_key: str, num_sessions: int, turns_per_session: int):
    """Run simulation only (no evaluation)."""
    from training.personas import get_persona
    from training.simulator import run_simulation

    persona = get_persona(persona_key)
    if not persona:
        print(f"Unknown persona: {persona_key}")
        print(f"Available: miguel, jake, ray, carlos, diana")
        sys.exit(1)

    _init_dbs()
    db = _get_db()

    print(f"Running simulation: {persona.name} ({persona.trade}/{persona.language})")
    print(f"  Sessions: {num_sessions}, Turns/session: {turns_per_session}")
    print(f"  Chaos probability: {persona.chaos_probability}")
    print()

    report = run_simulation(db, persona, num_sessions, turns_per_session)

    print(f"Simulation complete in {report.elapsed_seconds:.1f}s")
    print(f"  Tier progression: {report.tier_progression}")
    print(f"  Final tier: {report.final_profile.get('current_tier', '?')}")
    print(f"  Total turns: {report.final_profile.get('total_turns', '?')}")

    db.close()
    return report


def _run_evaluate(persona_key: str, num_sessions: int, turns_per_session: int, prompt_version: str):
    """Run simulation + full evaluation pipeline."""
    from training.personas import get_persona
    from training.simulator import run_simulation
    from training.evaluators import (
        ResponseEvaluator, HazardEvaluator, BehavioralEvaluator,
        AuthenticityEvaluator, ArcEvaluator, EvalContext,
    )
    from training.quality_gate import evaluate_quality_gate
    from training.report import format_terminal_report, save_json_report

    persona = get_persona(persona_key)
    if not persona:
        print(f"Unknown persona: {persona_key}")
        print(f"Available: miguel, jake, ray, carlos, diana")
        sys.exit(1)

    _init_dbs()
    db = _get_db()

    # Snapshot prompt version
    version_id = _snapshot_prompt_version(prompt_version)

    print(f"Running evaluation: {persona.name} ({persona.trade}/{persona.language})")
    print(f"  Sessions: {num_sessions}, Turns/session: {turns_per_session}")
    print(f"  Prompt version: {prompt_version}")
    print()

    # Phase 1: Run simulation
    start = time.monotonic()
    sim_report = run_simulation(db, persona, num_sessions, turns_per_session)
    print(f"Simulation complete ({sim_report.elapsed_seconds:.1f}s). Running evaluators...")

    # Phase 2: Run evaluators on every coaching response
    response_eval = ResponseEvaluator()
    hazard_eval = HazardEvaluator()
    behavioral_eval = BehavioralEvaluator()
    authenticity_eval = AuthenticityEvaluator()
    arc_evaluator = ArcEvaluator()

    response_evals = []
    hazard_evals = []
    behavioral_evals = []
    authenticity_evals = []
    stress_test_results = []

    for session in sim_report.sessions:
        # Build thread history incrementally
        thread_so_far = []

        for i, turn in enumerate(session.turns):
            thread_so_far.append(turn)

            if turn["role"] != "coach":
                continue

            # Find the preceding worker message
            worker_turn = session.turns[i - 1] if i > 0 else {}

            ctx = EvalContext(
                coaching_response=turn.get("text", ""),
                response_mode=turn.get("mode", ""),
                worker_message=worker_turn.get("text", ""),
                has_photo=worker_turn.get("has_photo", False),
                photo_id=session.photo_id,
                persona_name=persona.name,
                trade=persona.trade,
                experience_level=persona.experience_level,
                language=persona.language,
                worker_tier=session.tier_at_start,
                session_number=session.session_number,
                turn_number=turn.get("turn", 1),
                thread_history=list(thread_so_far),
                chaos_mode=worker_turn.get("chaos_mode"),
            )

            # Run all 4 per-response evaluators
            r_eval = response_eval.evaluate(ctx)
            response_evals.append(r_eval)

            h_eval = hazard_eval.evaluate(ctx)
            hazard_evals.append(h_eval)

            b_eval = behavioral_eval.evaluate(ctx)
            behavioral_evals.append(b_eval)

            a_eval = authenticity_eval.evaluate(ctx)
            authenticity_evals.append(a_eval)

            # Track stress test results for chaos turns
            if ctx.chaos_mode:
                # Did the coach handle it appropriately?
                handled = (
                    r_eval.pass_fail.get("no_first_person", True)
                    and r_eval.pass_fail.get("char_count_ok", True)
                    and authenticity_eval.evaluate(ctx).scores.get("sounds_human", 3) >= 2.5
                )
                stress_test_results.append({
                    "chaos_mode": ctx.chaos_mode,
                    "session": session.session_number,
                    "turn": ctx.turn_number,
                    "handled": handled,
                })

            print(f"  Evaluated session {session.session_number} turn {ctx.turn_number}", end="\r")

    print(f"\n  Per-response evaluation complete ({len(response_evals)} responses)")

    # Phase 3: Arc evaluation (full simulation)
    arc_ctx = EvalContext(
        persona_name=persona.name,
        trade=persona.trade,
        experience_level=persona.experience_level,
        language=persona.language,
        full_transcript=[s.__dict__ if hasattr(s, '__dict__') else
                         {"session_number": s.session_number,
                          "turns": s.turns,
                          "tier_at_start": s.tier_at_start,
                          "tier_at_end": s.tier_at_end}
                         for s in sim_report.sessions],
        tier_progression=sim_report.tier_progression,
        mentor_notes_history=sim_report.mentor_notes_history,
        final_profile=sim_report.final_profile,
    )
    arc_result = arc_evaluator.evaluate(arc_ctx)
    print(f"  Arc evaluation complete")

    # Phase 4: Quality Gate
    gate_report = evaluate_quality_gate(
        response_evals=response_evals,
        hazard_evals=hazard_evals,
        behavioral_evals=behavioral_evals,
        authenticity_evals=authenticity_evals,
        arc_eval=arc_result,
        stress_test_results=stress_test_results,
    )
    gate_report.total_responses_evaluated = len(response_evals)
    gate_report.total_sessions = num_sessions
    gate_report.persona_name = persona.name
    gate_report.elapsed_seconds = time.monotonic() - start

    # Phase 5: Report
    terminal_output = format_terminal_report(gate_report, prompt_version)
    print()
    print(terminal_output)

    # Save JSON report
    report_dir = Path(__file__).resolve().parent.parent / "training_reports"
    filepath = save_json_report(gate_report, report_dir, prompt_version)
    print(f"\nJSON report saved: {filepath}")

    # Save to training DB
    _save_evaluation_run(
        persona, gate_report, sim_report, version_id, prompt_version,
        response_evals, hazard_evals, behavioral_evals, authenticity_evals, arc_result,
    )

    db.close()
    return gate_report


def _save_evaluation_run(
    persona, gate_report, sim_report, version_id, prompt_version,
    response_evals, hazard_evals, behavioral_evals, authenticity_evals, arc_result,
):
    """Persist evaluation results to training DB."""
    from training.db import TrainingSession, init_training_db
    from training.models import EvaluationRun, EvaluationScore

    init_training_db()
    tdb = TrainingSession()

    ev_run = EvaluationRun(
        prompt_version_id=version_id,
        prompt_version_label=prompt_version,
        persona_key=persona.name.lower(),
        persona_name=persona.name,
        num_sessions=gate_report.total_sessions,
        num_responses_evaluated=gate_report.total_responses_evaluated,
        overall_status=gate_report.overall_status,
        overall_diagnosis=gate_report.overall_diagnosis,
        report_json=json.dumps(gate_report.to_dict()),
        finished_at=datetime.now(timezone.utc),
        elapsed_seconds=gate_report.elapsed_seconds,
    )
    tdb.add(ev_run)
    tdb.commit()
    tdb.refresh(ev_run)

    # Save individual evaluator scores
    all_evals = [
        *[(e, "response") for e in response_evals],
        *[(e, "hazard") for e in hazard_evals],
        *[(e, "behavioral") for e in behavioral_evals],
        *[(e, "authenticity") for e in authenticity_evals],
    ]
    if arc_result:
        all_evals.append((arc_result, "arc"))

    for eval_result, eval_name in all_evals:
        score = EvaluationScore(
            evaluation_run_id=ev_run.id,
            evaluator_name=eval_name,
            scores_json=json.dumps(eval_result.scores),
            pass_fail_json=json.dumps(eval_result.pass_fail) if eval_result.pass_fail else None,
            diagnosis=eval_result.diagnosis,
        )
        tdb.add(score)

    tdb.commit()
    tdb.close()


def _run_gate(num_sessions: int, turns_per_session: int, prompt_version: str):
    """Run full Quality Gate check across all personas."""
    personas = ["miguel", "jake", "ray"]
    results = {}

    for persona_key in personas:
        print(f"\n{'=' * 40}")
        print(f"  PERSONA: {persona_key.upper()}")
        print(f"{'=' * 40}")
        results[persona_key] = _run_evaluate(persona_key, num_sessions, turns_per_session, prompt_version)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  FULL QUALITY GATE SUMMARY")
    print(f"{'=' * 60}")
    for name, report in results.items():
        print(f"  {name:12s}: {report.overall_status}")
    print(f"{'=' * 60}")


def _show_report(latest: bool = False, run_id: int | None = None):
    """Display a past evaluation report."""
    if latest:
        # Find most recent JSON report
        report_dir = Path(__file__).resolve().parent.parent / "training_reports"
        if not report_dir.exists():
            print("No training_reports directory found.")
            return
        reports = sorted(report_dir.glob("qg_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            print("No reports found.")
            return
        filepath = reports[0]
        data = json.loads(filepath.read_text())
        print(f"Latest report: {filepath.name}")
        print(json.dumps(data, indent=2))
    elif run_id is not None:
        from training.db import TrainingSession, init_training_db
        from training.models import EvaluationRun
        init_training_db()
        tdb = TrainingSession()
        run = tdb.query(EvaluationRun).get(run_id)
        if run and run.report_json:
            print(json.dumps(json.loads(run.report_json), indent=2))
        else:
            print(f"No evaluation run found with id={run_id}")
        tdb.close()


def main():
    parser = argparse.ArgumentParser(
        prog="python -m training",
        description="Headless evaluation pipeline for coaching quality",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- evaluate ---
    eval_parser = subparsers.add_parser("evaluate", help="Run simulation + full evaluation")
    eval_parser.add_argument("persona", help="Persona key (miguel, jake, ray, carlos, diana)")
    eval_parser.add_argument("--sessions", type=int, default=10, help="Number of sessions")
    eval_parser.add_argument("--turns", type=int, default=4, help="Turns per session")
    eval_parser.add_argument("--prompt-version", default="current", help="Prompt version label")

    # --- simulate ---
    sim_parser = subparsers.add_parser("simulate", help="Run simulation only (no evaluation)")
    sim_parser.add_argument("persona", help="Persona key")
    sim_parser.add_argument("--sessions", type=int, default=10)
    sim_parser.add_argument("--turns", type=int, default=4)

    # --- gate ---
    gate_parser = subparsers.add_parser("gate", help="Run full Quality Gate (all personas)")
    gate_parser.add_argument("--sessions", type=int, default=10)
    gate_parser.add_argument("--turns", type=int, default=4)
    gate_parser.add_argument("--prompt-version", default="current")

    # --- report ---
    report_parser = subparsers.add_parser("report", help="View past evaluation reports")
    report_parser.add_argument("--latest", action="store_true", help="Show latest report")
    report_parser.add_argument("--run-id", type=int, help="Show report by evaluation run ID")

    args = parser.parse_args()

    if args.command == "evaluate":
        _run_evaluate(args.persona, args.sessions, args.turns, args.prompt_version)
    elif args.command == "simulate":
        _run_simulation(args.persona, args.sessions, args.turns)
    elif args.command == "gate":
        _run_gate(args.sessions, args.turns, args.prompt_version)
    elif args.command == "report":
        _show_report(latest=args.latest, run_id=args.run_id)


if __name__ == "__main__":
    main()
