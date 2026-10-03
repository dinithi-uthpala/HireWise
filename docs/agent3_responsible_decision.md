# Agent 3 - Responsible Decision Agent (reference)

Owner: Team leader. Code: `backend/agents/agent3_responsible_decision/`, `backend/api/agent3.py`,
`backend/api/pipeline.py`, `backend/models_pipeline.py`.

## Purpose
Make the system's output safe, explainable, privacy-aware and always subject to human review.
Agent 3 gives a **recommendation, never a hiring decision**. `human_review_required` is typed
`Literal[True]`, so a result that skips the human cannot be created.

## Position in the pipeline
CV file -> **Agent 1** (`ExtractionResult`) -> **Agent 2** (`MatchResult`) -> **Agent 3** (`ReviewOutput`)
-> database + audit log -> recruiter dashboard -> human decision.
Agents communicate through REST + JSON; every hop is validated by Pydantic models in `backend/schemas.py`.

## What Agent 3 checks
| Check | How | Failure result |
| --- | --- | --- |
| Privacy re-check | Regex scan for email, phone, national ID in the anonymous profile and redacted CV text; institution names and prohibited attributes (gender, religion, marital status, ...) in scoring evidence | `PRIVACY_CHECK_FAILED` -> manual review |
| Extraction confidence | `extraction_confidence` vs threshold (default 0.75) | `LOW_EXTRACTION_CONFIDENCE` -> manual review |
| Parse quality | `parse_status` failed / low_confidence | `PARSE_FAILED`, `LOW_QUALITY_PARSE` -> manual review |
| Matching confidence | Derived: 1.0, minus 0.10 per uncertain match (max 0.5), minus 0.15 if nothing retrieved, minus 0.15 if Agent 2 warned | `LOW_MATCHING_CONFIDENCE` -> manual review (threshold 0.55) |
| Score available | `match_score` is not None | `MATCH_UNAVAILABLE` -> manual review |
| Score integrity | Component points must add up to the final score (tolerance 1; over 5 is critical) | `SCORE_BREAKDOWN_MISMATCH` (warning), `SCORE_INCONSISTENT` (manual review) |
| Evidence exists | A component that earned points must have written evidence | `MISSING_SCORE_EVIDENCE` -> "Insufficient evidence" |
| Mandatory gaps | `skill_gaps` with category mandatory | `MISSING_MANDATORY_SKILLS` (warning) |
| Uncertain matches | Agent 2 `uncertain_matches` (never assumed true) | `UNCERTAIN_MATCHES` (warning) |
| Borderline score | Within 2 points of 80 or 60 | `BORDERLINE_SCORE` (warning; blocks "Strong") |
| Same candidate | extraction and match candidate IDs equal | `CANDIDATE_ID_MISMATCH` -> manual review |
| Ties / patterns | Across a job's candidates: same score; all same score (3+) | notes in the ranking list (never change a label) |

## Recommendation labels (there is NO "Rejected")
1. Any manual-review flag -> **Manual review required - do not rely on score alone**
2. Score below 60, or missing evidence -> **Insufficient job-related evidence - recruiter review required**
3. Score 80-100 and no warnings -> **Strong match - recruiter review required**
4. Otherwise (60-79, or 80+ with warnings) -> **Potential match - recruiter review required**

## Human decision and audit
- Recruiter chooses shortlist / hold / not selected. If the choice goes against the AI
  (shortlist without AI support, or not-select a Strong/Potential match) a **note is required** and the
  decision is marked as an **override**.
- Every step writes an audit event (agent1 extracted, agent2 scored, agent3 reviewed, user human_decision).
  Events hold **no personal data and no free-text notes**.
- The audit log is **hash-chained**: each entry stores the SHA-256 of the previous one, so editing or
  deleting any old entry is detected (`GET /api/audit-chain/verify`, `scripts/audit_tamper_demo.py`).

## Fairness test mode
`POST /api/pipeline/fairness-test` runs two CVs (same qualifications, different identity) through the
full pipeline. PASS needs a score difference within tolerance (default 0.5) and the same recommendation.
Sample pair: `samples/cvs/fairness_pair_a_male.docx`, `fairness_pair_b_female.docx`.

## LLM use in Agent 3 (optional, off by default)
The explanation is first built from fixed rules. If `LLM_PROVIDER` is `openai` or `gemini` with a key,
an LLM may re-word it. The rewrite is discarded unless it keeps every number, skill name, the
recommendation and the human-decision sentence, and adds no personal data, prohibited attribute or
"rejected". The LLM is never called if the privacy check failed. Its prompt contains only anonymous text.
A note is appended when LLM wording is used, and the audit event records `explanation_method`.

## Endpoints
`POST /api/agent3/review`, `POST /api/agent3/fairness-compare`, `GET /api/jobs/{job_id}/candidates`,
`GET /api/candidates/{id}`, `POST /api/candidates/{id}/decision`, `GET /api/audit/{id}`,
`GET /api/audit-chain/verify`, `POST /api/pipeline/run`, `POST /api/pipeline/fairness-test`.

## Known limitations (be honest in the report/viva)
- Matching confidence is derived by a simple heuristic because Agent 2 does not output one.
- Privacy re-check is pattern based; it cannot detect a person's name (Agent 1 handles names).
- A candidate ID comes from a hash of the CV, so the same CV uploaded for two jobs is overwritten.
- Access control (roles) is a placeholder in `backend/api/deps.py` until JWT login is integrated.
- The fairness test proves equal treatment for the tested pair only; it is not a full bias audit.

## Likely viva questions
1. *Does the AI decide who is hired?* No. Output is a recommendation; a human decides; the type system enforces it.
2. *Why is the score not produced by the LLM?* Fixed weights are auditable and repeatable (Agent 2). An LLM may only re-word.
3. *How do you know identity does not affect scoring?* PII is removed before scoring, Agent 3 re-checks, and the paired-CV fairness test.
4. *What if the LLM lies in the explanation?* The faithfulness check rejects any rewrite that changes facts; the rule-based text is kept.
5. *How is the audit trail protected?* Hash chain; edits or deletions break every later hash and are detected.
6. *What happens if a recruiter disagrees with the AI?* They can override; a note is required and it is logged.
