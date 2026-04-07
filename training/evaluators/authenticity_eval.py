"""Agent 6: Authenticity Judge — would a real foreman actually text this?

Scores naturalness, trade credibility, and conversational authenticity.
This evaluator should be brutal — if it reads like a chatbot, it fails.
"""

from __future__ import annotations

from training.evaluators.base import BaseEvaluator, EvalContext, EvalResult


class AuthenticityEvaluator(BaseEvaluator):
    """Evaluates whether coaching responses sound like a real construction professional."""

    name = "authenticity"
    model_tier = "haiku"

    def evaluate(self, context: EvalContext) -> EvalResult:
        result = EvalResult(evaluator=self.name)

        if not context.coaching_response:
            result.error = "No coaching response to evaluate"
            return result

        scores = self._evaluate_authenticity(context)
        result.scores = scores

        # Diagnosis
        if scores.get("sounds_human", 5) < 3:
            result.diagnosis = (
                "Response reads like a chatbot, not a person. "
                "Tune IDENTITY_BLOCK — add more natural text patterns."
            )
        elif scores.get("trade_credible", 5) < 3:
            result.diagnosis = (
                "Response lacks trade credibility. Someone in this trade "
                "would not believe the sender knows their work."
            )
        elif scores.get("conversational_flow", 5) < 3:
            result.diagnosis = (
                "Exchange feels like Q&A, not a real text conversation. "
                "Improve conversational flow in turn guidance."
            )
        else:
            result.diagnosis = "Response passes authenticity checks."

        return result

    def _evaluate_authenticity(self, context: EvalContext) -> dict[str, float]:
        """Use Claude to judge authenticity of the coaching response."""
        system = """\
You are a brutally honest authenticity judge. You have spent 20 years in \
construction — concrete, iron, cranes, excavation, the whole thing. You've \
seen a thousand safety texts and you know what real ones look like.

You are evaluating whether an AI coaching response would pass as a text from \
a real, experienced construction professional. Be harsh. If it sounds like \
a machine or a corporate safety manager, score it low.

Score these dimensions (1-5):

- sounds_human: Does this read like a text message from a PERSON, or a chatbot? \
Real texts are imperfect, direct, sometimes blunt. Chatbot texts are smooth, \
polished, and formulaic. 1 = obvious chatbot. 5 = indistinguishable from a real text.

- trade_credible: Would someone who works in this specific trade (ironworker, \
operating engineer, laborer, etc.) believe the sender knows their work? Does \
the language match the trade? 1 = generic safety speak. 5 = clearly knows the trade.

- tone_match: Is the tone professional but approachable? Not corporate, not \
too casual. Like a seasoned foreman — direct, knowledgeable, respectful. \
1 = corporate memo or frat bro. 5 = perfect foreman energy.

- conversational_flow: Does this feel like a real text exchange, or a Q&A \
session? Real conversations have rhythm — acknowledgment, observation, question. \
Robotic exchanges go question-answer-question-answer. 1 = robotic Q&A. 5 = natural flow.

Return ONLY valid JSON with these 4 keys (integer values 1-5)."""

        # Include thread history for conversational flow assessment
        thread_context = ""
        if context.thread_history:
            recent = context.thread_history[-6:]  # Last 3 exchanges
            lines = []
            for turn in recent:
                role = turn.get("role", "unknown")
                text = turn.get("text", "")
                lines.append(f"  {role}: {text}")
            thread_context = "Recent conversation:\n" + "\n".join(lines) + "\n\n"

        user = (
            f"{thread_context}"
            f"Worker message: {context.worker_message}\n"
            f"Worker trade: {context.trade} ({context.experience_level})\n"
            f"Coaching response: {context.coaching_response}\n"
            f"Response mode: {context.response_mode}\n\n"
            "Return JSON: {sounds_human, trade_credible, tone_match, conversational_flow}"
        )

        raw = self._call_claude(system, user, max_tokens=300)
        data = self._extract_json(raw) if raw else {}

        return {
            "sounds_human": self._safe_score(data.get("sounds_human"), 3.0),
            "trade_credible": self._safe_score(data.get("trade_credible"), 3.0),
            "tone_match": self._safe_score(data.get("tone_match"), 3.0),
            "conversational_flow": self._safe_score(data.get("conversational_flow"), 3.0),
        }
