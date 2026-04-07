"""Base evaluator — shared types and utilities for all evaluation agents.

Each evaluator makes its own Claude API call with its own system prompt.
No shared context between evaluators or with the coaching AI.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EvalContext:
    """Everything an evaluator needs to score a single coaching exchange."""

    # The coaching response under evaluation
    coaching_response: str = ""
    response_mode: str = ""

    # What prompted it
    worker_message: str = ""
    has_photo: bool = False
    photo_id: int | None = None

    # Persona / worker context
    persona_name: str = ""
    trade: str = ""
    experience_level: str = ""
    language: str = "en"
    worker_tier: int = 1

    # Session context
    session_number: int = 1
    turn_number: int = 1
    thread_history: list[dict] = field(default_factory=list)

    # For arc evaluation — entire simulation data
    full_transcript: list[dict] | None = None
    tier_progression: list[int] | None = None
    mentor_notes_history: list[str] | None = None
    final_profile: dict | None = None

    # Chaos mode metadata (for stress test tracking)
    chaos_mode: str | None = None


@dataclass
class EvalResult:
    """Structured output from any evaluator."""

    evaluator: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    pass_fail: dict[str, bool] = field(default_factory=dict)
    diagnosis: str = ""
    raw_notes: str = ""
    error: str | None = None

    @property
    def passed(self) -> bool:
        """True if all pass/fail checks passed (or none exist)."""
        if not self.pass_fail:
            return True
        return all(self.pass_fail.values())

    def to_dict(self) -> dict:
        return {
            "evaluator": self.evaluator,
            "scores": self.scores,
            "pass_fail": self.pass_fail,
            "diagnosis": self.diagnosis,
            "raw_notes": self.raw_notes,
            "error": self.error,
        }


class BaseEvaluator:
    """All evaluators inherit from this. Provides Claude API call helper."""

    name: str = "base"
    # Subclasses set this: "haiku" for fast evals, "sonnet" for deep reasoning
    model_tier: str = "haiku"

    _MODEL_MAP = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-20250514",
    }

    def evaluate(self, context: EvalContext) -> EvalResult:
        """Override in subclasses."""
        raise NotImplementedError

    def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1500,
        temperature: float = 0.1,
    ) -> str | None:
        """Make an independent Claude API call. Returns raw text or None on error."""
        if not settings.anthropic_api_key:
            return None

        import anthropic

        model = self._MODEL_MAP.get(self.model_tier, self._MODEL_MAP["haiku"])
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            logger.error("Evaluator %s Claude call failed: %s", self.name, e)
            return None

    def _extract_json(self, text: str) -> dict:
        """Extract JSON object from Claude response text."""
        if not text:
            return {}
        # Try to find JSON block
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def _safe_score(self, value, default: float = 0.0) -> float:
        """Safely convert a value to a float score."""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
