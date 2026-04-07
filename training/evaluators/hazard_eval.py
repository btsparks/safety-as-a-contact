"""Agent 3: Hazard Evaluator — independent hazard ground truth + comparison.

Analyzes the coaching context independently to determine what hazards are present,
then compares against what the coaching AI identified. Catches both missed hazards
and hallucinated ones.
"""

from __future__ import annotations

from training.evaluators.base import BaseEvaluator, EvalContext, EvalResult


class HazardEvaluator(BaseEvaluator):
    """Independently assesses hazards and compares to coaching AI's identification."""

    name = "hazard"
    model_tier = "haiku"

    def evaluate(self, context: EvalContext) -> EvalResult:
        result = EvalResult(evaluator=self.name)

        if not context.coaching_response:
            result.error = "No coaching response to evaluate"
            return result

        # If no photo and worker message is minimal, hazard eval has limited value
        if not context.has_photo and len(context.worker_message) < 10:
            result.scores = {
                "hazard_detection_accuracy": 3.0,
                "hallucination_rate": 5.0,
                "severity_calibration": 3.0,
                "trade_relevance": 3.0,
            }
            result.diagnosis = "Limited context (no photo, minimal text) — baseline scores."
            return result

        scores = self._evaluate_hazards(context)
        result.scores = scores

        # Diagnosis
        if scores.get("hallucination_rate", 5) < 3:
            result.diagnosis = "Coach may be inventing hazards not present in the context."
        elif scores.get("hazard_detection_accuracy", 5) < 3:
            result.diagnosis = "Coach missed real hazards visible in the context."
        elif scores.get("severity_calibration", 5) < 3:
            result.diagnosis = "Severity level doesn't match the actual risk. ALERT overused or underused."
        else:
            result.diagnosis = "Hazard identification aligns with context."

        return result

    def _evaluate_hazards(self, context: EvalContext) -> dict[str, float]:
        """Use Claude to independently assess hazards and compare to coaching response."""
        system = """\
You are an independent construction safety evaluator. You evaluate whether a \
coaching AI correctly identified hazards in a worker interaction.

You will receive:
1. The worker's message (and whether they sent a photo)
2. The coaching AI's response
3. The worker's trade and context

Your job: independently assess what hazards are likely present based on the \
worker's message and context, then compare to what the coaching AI said.

Score these dimensions (1-5):
- hazard_detection_accuracy: Did the coach identify real hazards that are \
actually present based on the worker's description? 5 = spot-on identification, \
1 = completely missed real hazards.
- hallucination_rate: Did the coach invent or exaggerate hazards that aren't \
supported by the evidence? 5 = no hallucination, everything mentioned is grounded. \
1 = invented hazards with no basis.
- severity_calibration: Does the severity level match reality? ALERT should only \
be used for imminent life-threatening danger — not overused. 5 = severity perfectly \
calibrated. 1 = wildly over- or under-reacting.
- trade_relevance: Does the hazard identification make sense for this worker's \
trade? An ironworker's hazards differ from an electrician's. 5 = trade-appropriate. \
1 = hazard identification ignores trade context.

Return ONLY valid JSON with these 4 keys (integer values 1-5)."""

        user = (
            f"Worker message: {context.worker_message}\n"
            f"Worker sent a photo: {context.has_photo}\n"
            f"Worker trade: {context.trade}\n"
            f"Worker experience: {context.experience_level}\n"
            f"Response mode used: {context.response_mode}\n"
            f"Coaching response: {context.coaching_response}\n\n"
            "Return JSON: {hazard_detection_accuracy, hallucination_rate, severity_calibration, trade_relevance}"
        )

        raw = self._call_claude(system, user, max_tokens=400)
        data = self._extract_json(raw) if raw else {}

        return {
            "hazard_detection_accuracy": self._safe_score(data.get("hazard_detection_accuracy"), 3.0),
            "hallucination_rate": self._safe_score(data.get("hallucination_rate"), 3.0),
            "severity_calibration": self._safe_score(data.get("severity_calibration"), 3.0),
            "trade_relevance": self._safe_score(data.get("trade_relevance"), 3.0),
        }
