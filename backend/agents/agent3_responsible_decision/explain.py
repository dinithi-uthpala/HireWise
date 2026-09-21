"""Agent 3 - plain-language explanation (template based, no LLM needed).

Refers to the candidate by ID only and never repeats personal data.
An LLM can later rewrite this text more nicely, but the FACTS in it always
come from the deterministic results above.
"""
from __future__ import annotations

from backend.schemas import ExtractionResult, MatchResult, PrivacyCheck, RiskFlag

# Appended (for transparency) whenever an LLM reworded the explanation.
LLM_NOTE = ("Note: the wording of this explanation was refined by an AI language model. "
            "All scores, flags and checks come from fixed rules, and a human recruiter "
            "makes the final decision.")


def _join(items: list[str], limit: int = 6) -> str:
    if not items:
        return "none"
    shown = ", ".join(items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def build_explanation(
    extraction: ExtractionResult,
    match: MatchResult,
    label: str,
    flags: list[RiskFlag],
    privacy: PrivacyCheck,
    matching_conf: float,
) -> str:
    parts: list[str] = []

    if match.match_score is None:
        parts.append(f"No reliable score could be produced for candidate {match.candidate_id}.")
    else:
        b = match.score_breakdown
        parts.append(
            f"Candidate {match.candidate_id} scored {match.match_score:.1f} out of 100. "
            f"Points by component: mandatory skills {b.mandatory_skills:.1f}, "
            f"experience {b.experience:.1f}, education and certifications {b.education:.1f}, "
            f"preferred skills {b.preferred_skills:.1f}."
        )

    missing_mand = [g.skill for g in match.skill_gaps if g.category == "mandatory"]
    missing_pref = [g.skill for g in match.skill_gaps if g.category == "preferred"]
    parts.append(
        f"Mandatory skills found: {_join(match.matched_mandatory_skills)}. "
        f"Mandatory skills not found: {_join(missing_mand)}. "
        f"Preferred skills found: {_join(match.matched_preferred_skills)}. "
        f"Preferred skills not found: {_join(missing_pref)}."
    )

    if match.uncertain_matches:
        reqs = [u.requirement for u in match.uncertain_matches]
        parts.append(
            f"{len(reqs)} requirement(s) could not be confirmed and were NOT assumed to be met: "
            f"{_join(reqs, 5)}."
        )

    parts.append(
        f"Data quality: extraction confidence {extraction.extraction_confidence:.0%}, "
        f"matching confidence {matching_conf:.0%}."
    )

    if privacy.passed:
        parts.append("Privacy check passed: no personal identifiers were found in the data used for scoring.")
    else:
        parts.append("Privacy check FAILED: " + "; ".join(privacy.violations) + ".")

    if flags:
        parts.append("Points for the recruiter to check: " + " ".join(f.message for f in flags))

    parts.append(
        f"Recommendation: {label}. This is decision support only. "
        "The final hiring decision is always made by a human recruiter."
    )
    return "\n\n".join(parts)
