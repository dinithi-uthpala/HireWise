"""Run every sample CV through Agents 1 -> 2 -> 3 and print the evaluation
table for the report. Nothing is saved to the database.

    python scripts/evaluate_agent3.py
    python scripts/evaluate_agent3.py --write      (also writes docs/evaluation_results.md)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agents.agent3_responsible_decision.fairness import compare_reviews  # noqa: E402
from backend.api.pipeline import run_agents  # noqa: E402
from backend.models import JobVacancy  # noqa: E402
from backend.schemas import ReviewThresholds  # noqa: E402

JOB = JobVacancy(
    job_id="JOB-EVAL", job_title="Junior Data Analyst",
    job_description=("Required skills: Python, SQL, Excel. Preferred skills: Pandas, Power BI. "
                     "Minimum 1 year of relevant experience. Bachelor's degree required."),
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    files = sorted(p for p in (ROOT / "samples" / "cvs").iterdir()
                   if p.suffix.lower() in {".pdf", ".docx", ".txt", ".md"})
    th = ReviewThresholds()
    lines = ["# HireWise evaluation results (sample CVs)", "",
             f"Job: {JOB.job_title}. Thresholds: strong >= {th.strong_match_min}, "
             f"potential >= {th.potential_match_min}.", "",
             "| Sample CV | Score | Recommendation | Risk flags | Privacy check |",
             "| --- | --- | --- | --- | --- |"]
    reviews = {}
    for p in files:
        try:
            _, _, review = run_agents(p.name, p.read_bytes(), JOB, th)
        except Exception as exc:
            lines.append(f"| {p.name} | - | ERROR ({type(exc).__name__}) | - | - |")
            continue
        reviews[p.name] = review
        flags = ", ".join(f.code for f in review.risk_flags) or "none"
        score = "n/a" if review.match_score is None else f"{review.match_score:.1f}"
        priv = "passed" if review.privacy_check.passed else "FAILED"
        lines.append(f"| {p.name} | {score} | {review.recommendation} | {flags} | {priv} |")

    a, b = reviews.get("fairness_pair_a_male.docx"), reviews.get("fairness_pair_b_female.docx")
    lines += ["", "## Fairness test (paired CVs)", ""]
    if a and b:
        r = compare_reviews("Pair A", "Pair B", a, b)
        lines += [f"- Score A: {r.score_a}, Score B: {r.score_b}, difference: {r.difference}",
                  f"- Result: {'PASS' if r.passed else 'FAIL'}", f"- {r.explanation}"]
    else:
        lines.append("Fairness pair files were not found or failed to process.")

    text = "\n".join(lines)
    print(text)
    if args.write:
        out = ROOT / "docs" / "evaluation_results.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"\nWritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
