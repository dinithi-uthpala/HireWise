"""Agent 3 - Responsible Decision Agent.

Ensures the system's output is safe, explainable, privacy-aware and always
subject to human review. It never makes the final hiring decision.
Responsibilities:
    - verify no sensitive/PII fields were used in scoring (privacy check)
    - check required scoring evidence and match/extraction confidence
    - apply human-review rules (low confidence, missing evidence, borderlines)
    - plain-language explanation + recommendation (Strong/Potential/Manual)
    - human override support + audit trail            (next step)
    - fairness test mode using paired CVs              (next step)

Input : ExtractionResult (Agent 1) + MatchResult (Agent 2) + thresholds
Output: ReviewOutput (recommendation + explanation + risk flags)
"""
from .agent import review_candidate

__all__ = ["review_candidate"]
