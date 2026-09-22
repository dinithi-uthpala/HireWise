"""Pure-logic tests: tie/pattern notes and the LLM faithfulness guard."""
from backend.agents.agent3_responsible_decision import review_candidate
from backend.agents.agent3_responsible_decision.explain import LLM_NOTE
from backend.agents.agent3_responsible_decision.llm_explain import (
    enhance_explanation,
    explanation_is_faithful,
)
from backend.agents.agent3_responsible_decision.patterns import batch_notes
from backend.schemas import SkillGap
from tests.test_agent3_review import make_extraction, make_match


# ------------------------------------------------------------- ties / patterns
def test_no_notes_when_scores_differ():
    notes = batch_notes({"A": 90.0, "B": 70.0, "C": 50.0})
    assert all(v == [] for v in notes.values())


def test_tied_scores_are_noted_for_both_candidates():
    notes = batch_notes({"A": 88.0, "B": 88.04, "C": 60.0})
    assert notes["A"] and notes["B"] and notes["C"] == []
    assert notes["A"][0].startswith("TIED_SCORE")


def test_identical_scores_across_three_or_more_is_unusual():
    notes = batch_notes({"A": 100.0, "B": 100.0, "C": 100.0})
    assert any(n.startswith("UNUSUAL_SCORE_PATTERN") for n in notes["A"])


def test_two_identical_scores_are_a_tie_not_an_unusual_pattern():
    notes = batch_notes({"A": 100.0, "B": 100.0})
    assert not any(n.startswith("UNUSUAL") for n in notes["A"])


def test_missing_scores_are_ignored():
    notes = batch_notes({"A": None, "B": None, "C": 50.0})
    assert notes == {"A": [], "B": [], "C": []}


# ------------------------------------------------------------- LLM guard
def _review(**match_kw):
    ext = make_extraction()
    match = make_match(**match_kw) if match_kw else make_match()
    return review_candidate(ext, match), match


def test_faithful_rewrite_is_accepted_and_labelled():
    review, match = _review()
    good = review.explanation.replace("Points by component:", "Here is how the points were earned:")
    out = enhance_explanation(review, match, lambda prompt: good)
    assert LLM_NOTE in out.explanation
    assert out.recommendation_code == review.recommendation_code      # facts untouched
    assert out.human_review_required is True


def test_rewrite_that_drops_the_score_is_rejected():
    review, match = _review()
    out = enhance_explanation(review, match, lambda p: "Great candidate, highly recommended for the human recruiter.")
    assert out.explanation == review.explanation


def test_rewrite_that_changes_a_number_is_rejected():
    review, match = _review()
    bad = review.explanation.replace("88.0", "97.0")
    assert bad != review.explanation
    assert enhance_explanation(review, match, lambda p: bad).explanation == review.explanation


def test_rewrite_that_adds_personal_data_or_rejection_is_rejected():
    review, match = _review()
    for evil in (review.explanation + " Contact kamal@example.com",
                 review.explanation + " This candidate is rejected.",
                 review.explanation + " She is a female applicant."):
        assert not explanation_is_faithful(review.explanation, evil, [])


def test_rewrite_must_keep_the_human_decision_sentence():
    review, match = _review()
    no_human = review.explanation.replace("human recruiter", "manager")
    assert enhance_explanation(review, match, lambda p: no_human).explanation == review.explanation


def test_llm_error_falls_back_to_rule_text():
    review, match = _review()

    def broken(prompt):
        raise RuntimeError("network down")

    assert enhance_explanation(review, match, broken).explanation == review.explanation


def test_llm_off_leaves_review_unchanged():
    review, match = _review()
    assert enhance_explanation(review, match, None) is review


def test_llm_can_rewrite_sanitized_explanation_when_privacy_check_failed():
    calls = []
    ext = make_extraction(summary="Reach me at kamal@example.com")
    match = make_match()
    review = review_candidate(ext, match)
    assert not review.privacy_check.passed
    out = enhance_explanation(review, match, lambda p: calls.append(p) or review.explanation)
    assert calls and "kamal@example.com" not in calls[0]
    assert out.explanation_method == "llm_reworded"


def test_prompt_sent_to_llm_contains_no_personal_data():
    sent = []
    review, match = _review()
    enhance_explanation(review, match, lambda p: sent.append(p) or None)
    assert sent and "@" not in sent[0] and review.candidate_id in sent[0]


def test_skills_are_required_terms():
    match = make_match(skill_gaps=[SkillGap(skill="Tableau", category="mandatory", reason="x")])
    review = review_candidate(make_extraction(), match)
    assert "Tableau" in review.explanation
    dropped = review.explanation.replace("Tableau", "a tool")
    assert enhance_explanation(review, match, lambda p: dropped).explanation == review.explanation
