"""Agent 5: Behavioral Science Auditor — evaluates against 8 behavioral frameworks.

This is what separates Safety as a Contact from a chatbot. Every coaching response
should demonstrate behavioral science principles, not just correct safety information.
"""

from __future__ import annotations

from training.evaluators.base import BaseEvaluator, EvalContext, EvalResult


class BehavioralEvaluator(BaseEvaluator):
    """Evaluates every response against the 8 behavioral science frameworks."""

    name = "behavioral"
    model_tier = "haiku"

    def evaluate(self, context: EvalContext) -> EvalResult:
        result = EvalResult(evaluator=self.name)

        if not context.coaching_response:
            result.error = "No coaching response to evaluate"
            return result

        scores = self._evaluate_frameworks(context)
        result.scores = scores

        # Composite score — weighted average across all 8
        weights = {
            "operant_conditioning": 1.0,
            "motivational_interviewing": 1.0,
            "self_determination": 1.0,
            "social_learning": 0.8,
            "psychological_safety": 1.5,  # Highest weight — if workers feel tested, product fails
            "fogg_behavior": 0.8,
            "nudge_theory": 0.8,
            "habit_loop": 0.8,
        }
        total_weight = sum(weights.values())
        composite = sum(
            scores.get(k, 3.0) * w for k, w in weights.items()
        ) / total_weight
        result.scores["behavioral_alignment_composite"] = round(composite, 2)

        # Diagnosis
        low_scores = {k: v for k, v in scores.items() if v < 2.5 and k in weights}
        if low_scores:
            worst = min(low_scores, key=low_scores.get)
            result.diagnosis = (
                f"Low behavioral alignment on: {', '.join(low_scores.keys())}. "
                f"Worst: {worst} ({low_scores[worst]}/5). "
                "Deep prompt problem — add explicit behavioral blocks."
            )
        elif composite < 3.5:
            result.diagnosis = (
                f"Composite behavioral score {composite}/5 is below threshold. "
                "Prompt architecture may need restructuring."
            )
        else:
            result.diagnosis = "Behavioral science alignment is adequate."

        return result

    def _evaluate_frameworks(self, context: EvalContext) -> dict[str, float]:
        """Use Claude to score against all 8 behavioral frameworks."""
        system = """\
You are a behavioral science auditor evaluating an AI safety coaching response \
for construction workers. This coaching system is built on 8 behavioral science \
frameworks. Score how well the response demonstrates each framework's principles.

The 8 frameworks and what to look for:

1. operant_conditioning: Does the response acknowledge the worker's action \
before coaching? Is reinforcement immediate? Does it reward the behavior of reporting?

2. motivational_interviewing: Is the approach collaborative, not directive? \
Does it express empathy? Does it support the worker's self-efficacy? Does it \
roll with resistance rather than confronting it?

3. self_determination: Is autonomy respected (worker chooses, not told)? \
Is competence built (scaffolded, not assumed)? Is relatedness fostered \
(connection to crew/team safety)?

4. social_learning: Is coaching scaffolded appropriately for the worker's \
experience level? Is the AI serving as a "More Knowledgeable Other" — \
guiding without lecturing?

5. psychological_safety: Is the tone blame-free? Does the worker feel safe, \
not tested? No surveillance feeling? No grading language? This is THE most \
important framework — if the worker feels evaluated, the product fails.

6. fogg_behavior: Is the coaching low-friction? Does it prompt a natural \
next action? Does it make the desired behavior (reporting, observing) easy?

7. nudge_theory: Does the response encourage the default desired behavior \
without restricting freedom? Good choice architecture?

8. habit_loop: Is the reward (the coaching response) immediate and valuable? \
Does it make the worker want to text again next time?

Score each framework 1-5:
1 = Violates the framework's principles
2 = Mostly ignores the framework
3 = Neutral — doesn't violate but doesn't demonstrate
4 = Good demonstration of the framework
5 = Excellent — textbook application

Return ONLY valid JSON with the 8 framework names as keys."""

        user = (
            f"Worker message: {context.worker_message}\n"
            f"Worker trade: {context.trade} ({context.experience_level})\n"
            f"Worker tier: {context.worker_tier}\n"
            f"Turn number: {context.turn_number}\n"
            f"Response mode: {context.response_mode}\n"
            f"Coaching response: {context.coaching_response}\n\n"
            "Return JSON with 8 keys (integer values 1-5): "
            "operant_conditioning, motivational_interviewing, self_determination, "
            "social_learning, psychological_safety, fogg_behavior, nudge_theory, habit_loop"
        )

        raw = self._call_claude(system, user, max_tokens=500)
        data = self._extract_json(raw) if raw else {}

        frameworks = [
            "operant_conditioning",
            "motivational_interviewing",
            "self_determination",
            "social_learning",
            "psychological_safety",
            "fogg_behavior",
            "nudge_theory",
            "habit_loop",
        ]
        return {f: self._safe_score(data.get(f), 3.0) for f in frameworks}
