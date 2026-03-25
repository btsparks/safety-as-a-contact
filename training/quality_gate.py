"""Quality Gate — aggregates all evaluator scores into a pass/fail scorecard.

A prompt version must pass ALL categories to be production-ready.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from training.evaluators.base import EvalResult


@dataclass
class CategoryResult:
    """Result for one quality gate category."""

    name: str
    status: str = "UNKNOWN"  # PASS, FAIL, WARN
    details: dict[str, float] = field(default_factory=dict)
    threshold_failures: list[str] = field(default_factory=list)
    diagnosis: str = ""


@dataclass
class QualityGateReport:
    """Complete quality gate scorecard."""

    categories: list[CategoryResult] = field(default_factory=list)
    overall_status: str = "UNKNOWN"  # PASS, CONDITIONAL_PASS, FAIL
    overall_diagnosis: str = ""

    # Raw counts
    total_responses_evaluated: int = 0
    total_sessions: int = 0
    persona_name: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status,
            "overall_diagnosis": self.overall_diagnosis,
            "total_responses_evaluated": self.total_responses_evaluated,
            "total_sessions": self.total_sessions,
            "persona_name": self.persona_name,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "categories": [
                {
                    "name": c.name,
                    "status": c.status,
                    "details": c.details,
                    "threshold_failures": c.threshold_failures,
                    "diagnosis": c.diagnosis,
                }
                for c in self.categories
            ],
        }


def _avg(values: list[float]) -> float:
    """Safe average."""
    return round(sum(values) / len(values), 2) if values else 0.0


def _rate(bools: list[bool]) -> float:
    """Pass rate as percentage."""
    return round(sum(bools) / len(bools) * 100, 1) if bools else 0.0


def evaluate_quality_gate(
    response_evals: list[EvalResult],
    hazard_evals: list[EvalResult],
    behavioral_evals: list[EvalResult],
    authenticity_evals: list[EvalResult],
    arc_eval: EvalResult | None = None,
    stress_test_results: list[dict] | None = None,
) -> QualityGateReport:
    """Aggregate all evaluator results into the Quality Gate scorecard."""
    report = QualityGateReport()

    # --- Category 1: Compliance (hard pass/fail) ---
    compliance = CategoryResult(name="Compliance")
    if response_evals:
        word_ok = [e.pass_fail.get("word_count_ok", True) for e in response_evals]
        char_ok = [e.pass_fail.get("char_count_ok", True) for e in response_evals]
        no_i = [e.pass_fail.get("no_first_person", True) for e in response_evals]
        no_prohibited = [e.pass_fail.get("no_prohibited_phrases", True) for e in response_evals]
        no_regs = [e.pass_fail.get("no_regulation_citations", True) for e in response_evals]
        no_judgments = [e.pass_fail.get("no_safety_judgments", True) for e in response_evals]

        compliance.details = {
            "word_count_pass_rate": _rate(word_ok),
            "char_count_pass_rate": _rate(char_ok),
            "no_first_person_rate": _rate(no_i),
            "no_prohibited_rate": _rate(no_prohibited),
            "no_regulations_rate": _rate(no_regs),
            "no_safety_judgments_rate": _rate(no_judgments),
        }

        # Threshold: 100% pass rate
        fails = []
        if _rate(word_ok) < 100:
            fails.append(f"word_count: {_rate(word_ok)}% (need 100%)")
        if _rate(char_ok) < 100:
            fails.append(f"char_count: {_rate(char_ok)}% (need 100%)")
        if _rate(no_i) < 100:
            fails.append(f"first_person: {_rate(no_i)}% (need 100%)")
        if _rate(no_prohibited) < 100:
            fails.append(f"prohibited_phrases: {_rate(no_prohibited)}% (need 100%)")
        if _rate(no_regs) < 100:
            fails.append(f"regulations: {_rate(no_regs)}% (need 100%)")
        if _rate(no_judgments) < 100:
            fails.append(f"safety_judgments: {_rate(no_judgments)}% (need 100%)")

        compliance.threshold_failures = fails
        compliance.status = "PASS" if not fails else "FAIL"
        compliance.diagnosis = "All compliance checks passed." if not fails else f"Failures: {'; '.join(fails)}"
    report.categories.append(compliance)

    # --- Category 2: Response Quality (graded) ---
    coaching = CategoryResult(name="Response Quality")
    if response_evals:
        has_q = [e.pass_fail.get("has_question", False) for e in response_evals]
        mode_scores = [e.scores.get("mode_appropriateness", 3.0) for e in response_evals]
        doc_scores = [e.scores.get("document_grounding", 3.0) for e in response_evals]
        no_tech = [e.scores.get("no_technical_advice", 3.0) for e in response_evals]
        spec_scores = [e.scores.get("specificity", 3.0) for e in response_evals]
        reply_scores = [e.scores.get("reply_invitation", 3.0) for e in response_evals]

        q_rate = _rate(has_q)
        coaching.details = {
            "question_ratio": q_rate,
            "mode_appropriateness_avg": _avg(mode_scores),
            "document_grounding_avg": _avg(doc_scores),
            "no_technical_advice_avg": _avg(no_tech),
            "specificity_avg": _avg(spec_scores),
            "reply_invitation_avg": _avg(reply_scores),
        }

        fails = []
        if q_rate < 75:
            fails.append(f"question_ratio: {q_rate}% (need >75%)")
        if _avg(mode_scores) < 4.0:
            fails.append(f"mode_appropriateness: {_avg(mode_scores)} (need >4.0)")
        if _avg(no_tech) < 4.0:
            fails.append(f"no_technical_advice: {_avg(no_tech)} (need >4.0)")
        if _avg(spec_scores) < 3.0:
            fails.append(f"specificity: {_avg(spec_scores)} (need >3.0)")

        coaching.threshold_failures = fails
        coaching.status = "PASS" if not fails else "FAIL"
    report.categories.append(coaching)

    # --- Category 3: Behavioral Science Alignment (graded) ---
    behavioral = CategoryResult(name="Behavioral Science")
    if behavioral_evals:
        composites = [e.scores.get("behavioral_alignment_composite", 3.0) for e in behavioral_evals]
        psych_safety = [e.scores.get("psychological_safety", 3.0) for e in behavioral_evals]

        # Individual framework minimums
        frameworks = [
            "operant_conditioning", "motivational_interviewing", "self_determination",
            "social_learning", "psychological_safety", "fogg_behavior",
            "nudge_theory", "habit_loop",
        ]
        framework_avgs = {}
        for f in frameworks:
            vals = [e.scores.get(f, 3.0) for e in behavioral_evals]
            framework_avgs[f] = _avg(vals)

        behavioral.details = {
            "composite_avg": _avg(composites),
            "psychological_safety_avg": _avg(psych_safety),
            **{f"fw_{k}": v for k, v in framework_avgs.items()},
        }

        fails = []
        if _avg(composites) < 3.5:
            fails.append(f"composite: {_avg(composites)} (need >3.5)")
        if _avg(psych_safety) < 4.0:
            fails.append(f"psychological_safety: {_avg(psych_safety)} (need >4.0)")
        low_fw = {k: v for k, v in framework_avgs.items() if v < 2.5}
        for k, v in low_fw.items():
            fails.append(f"{k}: {v} (need >2.5)")

        behavioral.threshold_failures = fails
        if not fails:
            behavioral.status = "PASS"
        elif len(fails) == 1 and "composite" not in fails[0]:
            behavioral.status = "WARN"
        else:
            behavioral.status = "FAIL"
    report.categories.append(behavioral)

    # --- Category 4: Authenticity (graded) ---
    auth = CategoryResult(name="Authenticity")
    if authenticity_evals:
        human = [e.scores.get("sounds_human", 3.0) for e in authenticity_evals]
        trade = [e.scores.get("trade_credible", 3.0) for e in authenticity_evals]
        flow = [e.scores.get("conversational_flow", 3.0) for e in authenticity_evals]

        auth.details = {
            "sounds_human_avg": _avg(human),
            "trade_credible_avg": _avg(trade),
            "conversational_flow_avg": _avg(flow),
        }

        fails = []
        if _avg(human) < 3.5:
            fails.append(f"sounds_human: {_avg(human)} (need >3.5)")
        if _avg(trade) < 3.0:
            fails.append(f"trade_credible: {_avg(trade)} (need >3.0)")
        if _avg(flow) < 3.5:
            fails.append(f"conversational_flow: {_avg(flow)} (need >3.5)")

        auth.threshold_failures = fails
        auth.status = "PASS" if not fails else "FAIL"
    report.categories.append(auth)

    # --- Category 5: Longitudinal Coherence (graded) ---
    longitudinal = CategoryResult(name="Longitudinal Coherence")
    if arc_eval and not arc_eval.error:
        longitudinal.details = dict(arc_eval.scores)

        fails = []
        if arc_eval.scores.get("coaching_evolution", 3.0) < 3.0:
            fails.append(f"coaching_evolution: {arc_eval.scores['coaching_evolution']} (need >3.0)")
        if arc_eval.scores.get("mentor_notes_accuracy", 3.0) < 3.0:
            fails.append(f"mentor_notes_accuracy: {arc_eval.scores['mentor_notes_accuracy']} (need >3.0)")
        if arc_eval.scores.get("program_coherence", 3.0) < 3.5:
            fails.append(f"program_coherence: {arc_eval.scores['program_coherence']} (need >3.5)")

        longitudinal.threshold_failures = fails
        longitudinal.status = "PASS" if not fails else "FAIL"
        longitudinal.diagnosis = arc_eval.diagnosis
    report.categories.append(longitudinal)

    # --- Category 6: Stress Test Survival (pass/fail) ---
    stress = CategoryResult(name="Stress Test")
    if stress_test_results:
        total = len(stress_test_results)
        passed = sum(1 for r in stress_test_results if r.get("handled", False))
        rate = round(passed / total * 100, 1) if total else 0

        stress.details = {
            "total_stress_tests": float(total),
            "passed": float(passed),
            "handling_rate": rate,
        }

        fails = []
        if rate < 90:
            fails.append(f"handling_rate: {rate}% (need >90%)")

        stress.threshold_failures = fails
        stress.status = "PASS" if not fails else "FAIL"
    report.categories.append(stress)

    # --- Overall verdict ---
    statuses = [c.status for c in report.categories if c.status != "UNKNOWN"]
    if not statuses:
        report.overall_status = "UNKNOWN"
        report.overall_diagnosis = "No evaluations completed."
    elif all(s == "PASS" for s in statuses):
        report.overall_status = "PASS"
        report.overall_diagnosis = "All quality gate categories passed."
    elif "FAIL" in statuses:
        failed = [c.name for c in report.categories if c.status == "FAIL"]
        report.overall_status = "FAIL"
        report.overall_diagnosis = f"Failed categories: {', '.join(failed)}"
    else:
        warned = [c.name for c in report.categories if c.status == "WARN"]
        report.overall_status = "CONDITIONAL_PASS"
        report.overall_diagnosis = f"Warnings in: {', '.join(warned)} — fix before production."

    return report
