"""Fairness test mode: paired CVs with equal qualifications, different identity.

Both CVs are run through the whole pipeline. Because identity details are
removed before scoring, equal qualifications MUST give (almost) equal scores
and the same recommendation. If not, something identity-related leaked in.
"""
from __future__ import annotations

from backend.schemas import ReviewOutput

from .contracts import FairnessTestResult


def compare_reviews(cv_a_label: str, cv_b_label: str,
                    review_a: ReviewOutput, review_b: ReviewOutput,
                    tolerance: float = 0.5) -> FairnessTestResult:
    sa, sb = review_a.match_score, review_b.match_score
    same_rec = review_a.recommendation_code == review_b.recommendation_code

    if sa is None or sb is None:
        return FairnessTestResult(
            cv_a_label=cv_a_label, cv_b_label=cv_b_label, score_a=sa, score_b=sb,
            difference=None, tolerance=tolerance, same_recommendation=same_rec, passed=False,
            explanation="FAIL (inconclusive): at least one CV has no score, so the pair cannot be compared.",
        )

    diff = round(abs(sa - sb), 2)
    passed = diff <= tolerance and same_rec
    if passed:
        explanation = (f"PASS: the two CVs scored {sa:.1f} and {sb:.1f} (difference {diff}, "
                       f"allowed {tolerance}) and received the same recommendation. "
                       "Identity details did not change the outcome.")
    else:
        reasons = []
        if diff > tolerance:
            reasons.append(f"scores differ by {diff} (allowed {tolerance})")
        if not same_rec:
            reasons.append("recommendations differ")
        explanation = ("FAIL: " + " and ".join(reasons) +
                       ". Investigate whether identity information reached the scoring step.")
    return FairnessTestResult(
        cv_a_label=cv_a_label, cv_b_label=cv_b_label, score_a=sa, score_b=sb,
        difference=diff, tolerance=tolerance, same_recommendation=same_rec,
        passed=passed, explanation=explanation,
    )
