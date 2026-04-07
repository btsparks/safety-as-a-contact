"""Agent 7: Arc Evaluator — longitudinal trajectory assessment.

Runs ONCE per simulation (after all sessions complete). Evaluates whether the
coaching demonstrates a real coaching ARC over time — not just individual good
responses, but a coherent developmental program.

This is the most important evaluator. Uses Sonnet for deeper reasoning.
"""

from __future__ import annotations

import json

from training.evaluators.base import BaseEvaluator, EvalContext, EvalResult


class ArcEvaluator(BaseEvaluator):
    """Evaluates the longitudinal coaching trajectory across an entire simulation."""

    name = "arc"
    model_tier = "sonnet"  # Deeper reasoning needed for arc analysis

    def evaluate(self, context: EvalContext) -> EvalResult:
        result = EvalResult(evaluator=self.name)

        if not context.full_transcript:
            result.error = "No full transcript provided — arc evaluation requires complete simulation data"
            return result

        scores = self._evaluate_arc(context)
        result.scores = scores

        # Diagnosis
        if scores.get("program_coherence", 5) < 3:
            result.diagnosis = (
                "No visible coaching arc. Individual responses may be fine but "
                "there is no developmental program. System/program problem — "
                "fix tier calc, mentor notes gen, session management."
            )
        elif scores.get("coaching_evolution", 5) < 3:
            result.diagnosis = (
                "Coaching approach does not visibly change as the worker grows. "
                "Tier-adapted instructions may not be strong enough."
            )
        elif scores.get("mentor_notes_accuracy", 5) < 3:
            result.diagnosis = (
                "Mentor notes don't accurately reflect what happened in conversations. "
                "Fix mentor notes generation in profile.py."
            )
        else:
            result.diagnosis = "Longitudinal coaching arc is coherent."

        return result

    def _evaluate_arc(self, context: EvalContext) -> dict[str, float]:
        """Use Claude (Sonnet) to evaluate the full coaching arc."""
        system = """\
You are evaluating a longitudinal AI safety coaching simulation. You will see \
the COMPLETE transcript of a multi-session coaching relationship between an AI \
coach and a simulated construction worker.

This is NOT about individual response quality. This is about whether the \
coaching demonstrates a DEVELOPMENTAL ARC — does the AI's approach change \
as the worker grows? Is there a visible coaching program, or just a series \
of disconnected exchanges?

Score these dimensions (1-5):

- coaching_evolution: Did the AI's coaching approach visibly change as the \
worker developed? Early sessions should be more scaffolded (more questions, \
simpler). Later sessions should challenge the worker more. 1 = same approach \
from start to finish. 5 = clearly adapts over time.

- mentor_notes_accuracy: Do the mentor notes accurately reflect what actually \
happened in the conversations? Do they capture the worker's real patterns, \
growth, and challenges? 1 = generic/inaccurate notes. 5 = precise reflection.

- tier_progression_logic: Did tier changes happen at appropriate inflection \
points? Did the worker earn tier changes through demonstrated growth, or did \
tiers change arbitrarily? 1 = random tier changes. 5 = well-calibrated progression.

- worker_language_shift: Looking at the worker's messages over time — did they \
shift from passive to assertive? Vague to specific? This tests whether the \
COACHING is actually working. 1 = no change. 5 = clear language evolution.

- relationship_building: Does the AI's tone with this specific worker feel like \
a developing relationship? Does it remember context, build on previous sessions, \
refer to shared history? 1 = transactional/generic. 5 = genuine relationship.

- program_coherence: Across all sessions, is there a visible coaching arc with \
purpose and direction? Could you describe "the story" of this coaching \
relationship? 1 = no arc, just random exchanges. 5 = clear developmental narrative.

Return ONLY valid JSON with these 6 keys (integer values 1-5)."""

        # Build a condensed transcript for the AI to evaluate
        transcript_summary = self._build_transcript_summary(context)

        user = (
            f"Persona: {context.persona_name} ({context.trade}, {context.experience_level})\n"
            f"Language: {context.language}\n"
            f"Tier progression: {context.tier_progression}\n\n"
            f"Mentor notes over time:\n"
        )

        if context.mentor_notes_history:
            for i, notes in enumerate(context.mentor_notes_history, 1):
                if notes:
                    user += f"  After session {i}: {notes[:200]}\n"

        user += f"\n{transcript_summary}\n\n"
        user += (
            "Return JSON: {coaching_evolution, mentor_notes_accuracy, "
            "tier_progression_logic, worker_language_shift, relationship_building, "
            "program_coherence}"
        )

        raw = self._call_claude(system, user, max_tokens=800)
        data = self._extract_json(raw) if raw else {}

        keys = [
            "coaching_evolution",
            "mentor_notes_accuracy",
            "tier_progression_logic",
            "worker_language_shift",
            "relationship_building",
            "program_coherence",
        ]
        return {k: self._safe_score(data.get(k), 3.0) for k in keys}

    def _build_transcript_summary(self, context: EvalContext) -> str:
        """Build a condensed but complete transcript for arc evaluation."""
        lines = ["FULL SIMULATION TRANSCRIPT:"]

        for session in (context.full_transcript or []):
            session_num = session.get("session_number", "?")
            tier_start = session.get("tier_at_start", "?")
            tier_end = session.get("tier_at_end", "?")
            lines.append(
                f"\n--- Session {session_num} (tier {tier_start} → {tier_end}) ---"
            )

            for turn in session.get("turns", []):
                role = turn.get("role", "?")
                text = turn.get("text", "")
                photo_tag = " [photo]" if turn.get("has_photo") else ""
                mode_tag = f" [{turn['mode']}]" if turn.get("mode") else ""
                lines.append(f"  {role}{photo_tag}{mode_tag}: {text}")

        return "\n".join(lines)
