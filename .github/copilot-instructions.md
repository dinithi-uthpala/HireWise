# HireWise - rules for AI assistants

HireWise = 3-agent HR shortlisting system. Backend: FastAPI (backend/). Frontend: Streamlit (frontend/).
Agent 1 extracts+anonymizes CVs, Agent 2 scores vs a job, Agent 3 reviews (privacy, risk flags,
recommendation). The AI NEVER makes the final hiring decision.

## Rules
- Do not edit Agent 1 or Agent 2 code, backend/schemas.py, .env or any secrets.
- Never show or generate a "Rejected" label. Show recommendation text exactly as returned.
- Always show: "Recruiter review required".
- No personal data in logs or audit entries. Keep code simple and commented: I must explain it in a viva.
- After changes, tell me to run: python -m pytest tests -q

## Backend API (base URL comes from the existing frontend config; reuse it)
- POST /api/agent2/jobs  JSON {job_id?, job_title, job_description} -> 201; 409 if job_id exists
- POST /api/pipeline/run  multipart: job_id + files[] -> [{filename, status:"processed"|"error", candidate, error}]
- GET  /api/jobs/{job_id}/candidates -> [{candidate_id, job_id, match_score, recommendation_code,
       recommendation, extraction_confidence, risk_flag_codes[], status, final_decision}]
- GET  /api/candidates/{id} -> {summary, extraction, match:{match_score, score_breakdown{mandatory_skills,
       experience,education,preferred_skills}, matched_mandatory_skills[], matched_preferred_skills[],
       skill_gaps[{skill,category,reason}], uncertain_matches[{requirement,reason}], warnings[]},
       review:{explanation, risk_flags[{code,severity,message}], privacy_check{passed,violations[]},
       matching_confidence}, decisions[]}
- POST /api/candidates/{id}/decision JSON {decision:"shortlist"|"hold"|"not_selected", note} -> 200;
       422 {detail} when a note is required (decision differs from AI); 404 unknown candidate
- GET  /api/audit/{id} -> [{id, actor, action, summary, ts, entry_hash}]
- GET  /api/audit-chain/verify -> {valid, entries_checked, first_bad_entry_id}
- POST /api/pipeline/fairness-test multipart: job_id, tolerance, file_a, file_b ->
       {score_a, score_b, difference, passed, explanation}

       - Streamlit reruns the whole script on every click: keep loaded data in st.session_state,
  never nest st.button inside another st.button's if-block, use st.form for forms.
- Decision values sent to the API are lowercase: shortlist | hold | not_selected.