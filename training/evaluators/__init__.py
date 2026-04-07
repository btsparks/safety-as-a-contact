"""Evaluation agents for the headless coaching quality pipeline.

Each evaluator is an independent agent with its own Claude API call and system prompt.
The coaching AI (Agent 2) never knows it's being evaluated.
"""

from training.evaluators.base import BaseEvaluator, EvalContext, EvalResult
from training.evaluators.response_eval import ResponseEvaluator
from training.evaluators.hazard_eval import HazardEvaluator
from training.evaluators.behavioral_eval import BehavioralEvaluator
from training.evaluators.authenticity_eval import AuthenticityEvaluator
from training.evaluators.arc_eval import ArcEvaluator

__all__ = [
    "BaseEvaluator",
    "EvalContext",
    "EvalResult",
    "ResponseEvaluator",
    "HazardEvaluator",
    "BehavioralEvaluator",
    "AuthenticityEvaluator",
    "ArcEvaluator",
]
