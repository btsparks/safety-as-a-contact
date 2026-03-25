"""Agent 4: Response Evaluator — mechanical/structural scoring of coaching responses.

Scores each response against hard, measurable criteria. Most checks are rule-based
(no AI needed). Mode appropriateness, document grounding, and tier alignment use a Claude call.

Updated for the document-grounded + behavioral reflection model.
"""

from __future__ import annotations

import re

from backend.coaching.prompts import PROHIBITED_PHRASES
from training.evaluators.base import BaseEvaluator, EvalContext, EvalResult


# First-person patterns — match word boundary to avoid false positives in
# words like "naïve" or Spanish "viste"
_FIRST_PERSON_PATTERN = re.compile(
    r"\b("
    r"I\s|I'[mdvlst]|I\s+can|I\s+see|I\s+notice|I\s+think|I\s+would|"
    r"so\s+I\b|let\s+me\b|Let\s+me\b"
    r")",
    re.IGNORECASE,
)

# OSHA / regulation patterns
_REGULATION_PATTERN = re.compile(
    r"\b(OSHA|29\s*CFR|1926\.\d+|1910\.\d+|ANSI|NFPA|regulation|standard|policy|code of federal)\b",
    re.IGNORECASE,
)

# Safety judgment patterns — the AI should never make safety evaluations
_SAFETY_JUDGMENT_PATTERN = re.compile(
    r"("
    r"that\s+(looks?\s+)?unsafe|that('s|\s+is)\s+a\s+hazard|"
    r"that\s+needs\s+to\s+be\s+fixed|you\s+need\s+to|"
    r"that\s+(looks?\s+)?dangerous|that\s+is\s+dangerous|"
    r"load\s+capacity|sling\s+angle|soil\s+type|wind\s+limit|"
    r"bearing\s+surface|shoring\s+adequa"
    r")",
    re.IGNORECASE,
)


class ResponseEvaluator(BaseEvaluator):
    """Scores coaching responses against mechanical/structural rules."""

    name = "response"
    model_tier = "haiku"

    def evaluate(self, context: EvalContext) -> EvalResult:
        text = context.coaching_response
        result = EvalResult(evaluator=self.name)

        if not text:
            result.error = "Empty coaching response"
            return result

        # --- Pass/fail checks (no AI needed) ---

        word_count = len(text.split())
        char_count = len(text)

        result.pass_fail["word_count_ok"] = 25 <= word_count <= 50
        result.pass_fail["char_count_ok"] = char_count <= 320
        result.pass_fail["no_first_person"] = not bool(_FIRST_PERSON_PATTERN.search(text))
        result.pass_fail["no_regulation_citations"] = not bool(_REGULATION_PATTERN.search(text))

        # Prohibited phrases check
        text_lower = text.lower()
        violations = [p for p in PROHIBITED_PHRASES if p.lower() in text_lower]
        result.pass_fail["no_prohibited_phrases"] = len(violations) == 0

        # No safety judgments (AI should never evaluate safety)
        result.pass_fail["no_safety_judgments"] = not bool(_SAFETY_JUDGMENT_PATTERN.search(text))

        # Has question
        result.pass_fail["has_question"] = "?" in text

        # Store raw metrics
        result.scores["word_count"] = float(word_count)
        result.scores["char_count"] = float(char_count)
        result.scores["prohibited_violations"] = float(len(violations))

        # --- Graded scores (AI-powered) ---
        ai_scores = self._evaluate_graded(context)
        result.scores.update(ai_scores)

        # Diagnosis
        fails = [k for k, v in result.pass_fail.items() if not v]
        if fails:
            result.diagnosis = f"Compliance failures: {', '.join(fails)}"
            if violations:
                result.diagnosis += f". Prohibited phrases found: {violations}"
        elif ai_scores.get("no_technical_advice", 5) < 3:
            result.diagnosis = "Response may contain technical advice from AI training."
        elif ai_scores.get("document_grounding", 5) < 3:
            result.diagnosis = "Document references missing or poorly attributed."
        else:
            result.diagnosis = "Response passes all mechanical checks."

        return result

    def _evaluate_graded(self, context: EvalContext) -> dict[str, float]:
        """Use Claude to evaluate subjective quality metrics."""
        system = """\
You are a quality evaluator for a construction safety SMS system that uses a \
document-grounded + behavioral reflection model. The AI is a resource assistant \
that connects workers to uploaded safety documents and asks reflective questions. \
It has NO trade expertise and NEVER makes safety judgments.

Score the coaching response on these 5 dimensions. Return ONLY valid JSON.

Scoring criteria:
- mode_appropriateness (1-5): Was the selected response mode (reference/reflect/connect) \
correct? REFERENCE when documents were available. REFLECT when no documents match. \
CONNECT when trade mismatch or behavioral pattern worth noting.
- document_grounding (1-5): If documents were referenced, were they properly attributed? \
1 = no attribution or fabricated reference. 3 = mentioned but vague. \
5 = clear source attribution ("Your site safety plan says..." or "Per [document]..."). \
If no documents were referenced (reflect mode), score 3 (neutral).
- no_technical_advice (1-5): Does the response avoid giving technical/engineering advice \
from the AI's own training? 1 = response contains specific technical guidance (load \
calculations, sling angles, soil assessments). 5 = purely reflective questions and \
document references, zero technical authority.
- specificity (1-5): Does the response reference something specific from the context, \
or is it generic? 1 = could apply to any situation. 5 = clearly references this exact situation.
- reply_invitation (1-5): Does the response invite the worker to respond, or is it a dead end? \
1 = statement with no opening. 5 = engaging reflective question."""

        user = (
            f"Worker message: {context.worker_message}\n"
            f"Has photo: {context.has_photo}\n"
            f"Worker trade: {context.trade}\n"
            f"Worker tier: {context.worker_tier}\n"
            f"Turn number: {context.turn_number}\n"
            f"Response mode selected: {context.response_mode}\n"
            f"Coaching response: {context.coaching_response}\n\n"
            "Return JSON with keys: mode_appropriateness, document_grounding, "
            "no_technical_advice, specificity, reply_invitation (all 1-5 integers)"
        )

        raw = self._call_claude(system, user, max_tokens=300)
        data = self._extract_json(raw) if raw else {}

        return {
            "mode_appropriateness": self._safe_score(data.get("mode_appropriateness"), 3.0),
            "document_grounding": self._safe_score(data.get("document_grounding"), 3.0),
            "no_technical_advice": self._safe_score(data.get("no_technical_advice"), 3.0),
            "specificity": self._safe_score(data.get("specificity"), 3.0),
            "reply_invitation": self._safe_score(data.get("reply_invitation"), 3.0),
        }
