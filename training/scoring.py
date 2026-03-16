"""Shared auto-scoring functions for coaching responses."""

from backend.coaching.prompts import PROHIBITED_PHRASES

# Phrases that indicate a generic (non-specific) response
GENERIC_PHRASES = [
    "looks good",
    "be safe",
    "stay alert",
    "stay safe",
    "keep it up",
    "keep up the good work",
    "nice work",
    "well done",
    "based on what I see",
    "from what I can tell",
    "in this image",
    "in the photo",
]


def score_length_ok(text: str) -> bool:
    """Response should be 25-320 characters (1-2 SMS segments)."""
    return 25 <= len(text) <= 320


def score_has_question(text: str) -> bool:
    """Default coaching mode is questioning (3:1 ratio)."""
    return "?" in text


def score_is_specific(text: str) -> bool:
    """Response should reference something specific, not be generic."""
    lower = text.lower()
    return not any(phrase.lower() in lower for phrase in GENERIC_PHRASES)


def score_no_prohibited(text: str) -> bool:
    """No prohibited language from the prompt architecture."""
    lower = text.lower()
    return not any(phrase.lower() in lower for phrase in PROHIBITED_PHRASES)


def score_mode_match(actual_mode: str, recommended_mode: str | None) -> bool | None:
    """Does the engine's mode match the scene analysis recommendation?"""
    if not recommended_mode:
        return None
    return actual_mode == recommended_mode


def compute_auto_scores(
    text: str,
    mode: str,
    recommended_mode: str | None = None,
) -> dict:
    """Compute all auto-scores and return as a dict."""
    length = score_length_ok(text)
    question = score_has_question(text)
    specific = score_is_specific(text)
    prohibited = score_no_prohibited(text)
    mode_ok = score_mode_match(mode, recommended_mode)

    total = sum([length, question, specific, prohibited])
    if mode_ok is not None:
        total += int(mode_ok)
    max_possible = 5 if mode_ok is not None else 4

    return {
        "score_length_ok": length,
        "score_has_question": question,
        "score_is_specific": specific,
        "score_no_prohibited": prohibited,
        "score_mode_match": mode_ok,
        "auto_score_total": total,
        "max_possible": max_possible,
    }
