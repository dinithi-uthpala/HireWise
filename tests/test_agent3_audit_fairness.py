"""Pure-logic tests: audit hash chain, override rule, fairness comparison."""
from types import SimpleNamespace

from backend.agents.agent3_responsible_decision import review_candidate
from backend.agents.agent3_responsible_decision.audit_chain import (
    GENESIS_HASH,
    compute_entry_hash,
    verify_chain,
)
from backend.agents.agent3_responsible_decision.decisions import is_override
from backend.agents.agent3_responsible_decision.fairness import compare_reviews
from tests.test_agent3_review import make_extraction, make_match


def _row(i, prev, action, summary="{}", cid="CAND-001", actor="agent1", ts="2026-09-21T10:00:00+00:00"):
    h = compute_entry_hash(prev, cid, actor, action, summary, ts)
    return SimpleNamespace(id=i, candidate_id=cid, actor=actor, action=action,
                           summary_json=summary, ts=ts, prev_hash=prev, entry_hash=h)


def _chain():
    r1 = _row(1, GENESIS_HASH, "extracted")
    r2 = _row(2, r1.entry_hash, "scored", actor="agent2")
    r3 = _row(3, r2.entry_hash, "reviewed", actor="agent3")
    return [r1, r2, r3]


# ------------------------------------------------------------- audit chain
def test_untouched_chain_is_valid():
    assert verify_chain(_chain()) == (True, None)


def test_empty_chain_is_valid():
    assert verify_chain([]) == (True, None)


def test_editing_an_old_entry_is_detected():
    rows = _chain()
    rows[1].summary_json = '{"match_score": 99}'
    assert verify_chain(rows) == (False, 2)


def test_deleting_an_entry_is_detected():
    rows = _chain()
    del rows[1]
    ok, bad = verify_chain(rows)
    assert ok is False and bad == 3


def test_reordering_entries_is_detected():
    rows = _chain()
    rows[0], rows[1] = rows[1], rows[0]
    assert verify_chain(rows)[0] is False


# ------------------------------------------------------------- override rule
def test_override_rules():
    assert is_override("STRONG_MATCH", "not_selected") is True
    assert is_override("POTENTIAL_MATCH", "not_selected") is True
    assert is_override("INSUFFICIENT_EVIDENCE", "shortlist") is True
    assert is_override("MANUAL_REVIEW", "shortlist") is True
    assert is_override("STRONG_MATCH", "shortlist") is False
    assert is_override("MANUAL_REVIEW", "not_selected") is False
    for code in ("STRONG_MATCH", "POTENTIAL_MATCH", "INSUFFICIENT_EVIDENCE", "MANUAL_REVIEW"):
        assert is_override(code, "hold") is False


# ------------------------------------------------------------- fairness
def _review(score, cid="CAND-001"):
    parts = (score * .45, score * .25, score * .15, score * .15)
    return review_candidate(make_extraction(cid=cid), make_match(score, parts, cid=cid))


def test_identical_scores_pass_fairness():
    res = compare_reviews("Pair A", "Pair B", _review(88, "CAND-A"), _review(88, "CAND-B"))
    assert res.passed and res.difference == 0
    assert res.explanation.startswith("PASS")


def test_different_scores_fail_fairness():
    res = compare_reviews("Pair A", "Pair B", _review(88, "CAND-A"), _review(70, "CAND-B"))
    assert not res.passed
    assert res.explanation.startswith("FAIL")


def test_small_difference_within_tolerance_passes():
    res = compare_reviews("A", "B", _review(88, "CAND-A"), _review(88.3, "CAND-B"), tolerance=0.5)
    assert res.passed


def test_same_score_but_different_recommendation_fails():
    a = _review(88, "CAND-A")
    b = _review(88, "CAND-B")
    b.recommendation_code = "MANUAL_REVIEW"
    assert not compare_reviews("A", "B", a, b).passed


def test_missing_score_is_inconclusive_not_a_pass():
    a = _review(88, "CAND-A")
    b = review_candidate(make_extraction(cid="CAND-B"),
                         make_match(None, cid="CAND-B", match_status="unavailable"))
    res = compare_reviews("A", "B", a, b)
    assert res.passed is False and res.difference is None
