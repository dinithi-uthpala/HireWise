"""Candidate results and recruiter review."""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

try:
  from frontend.auth import auth_headers, require_login
except ModuleNotFoundError:
  from auth import auth_headers, require_login

try:
  from frontend.job_selection import select_saved_job
except ModuleNotFoundError:
  from job_selection import select_saved_job

require_login()

try:
  from frontend.reporting import candidate_pdf
except ModuleNotFoundError:
  from reporting import candidate_pdf

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def response_detail(response: requests.Response) -> str:
  """Return the backend's useful error text when available."""
  try:
    body = response.json()
  except ValueError:
    return f"HTTP {response.status_code}"
  return str(body.get("detail") or f"HTTP {response.status_code}")


def load_candidates(job_id: str) -> list[dict]:
  with st.spinner("Loading candidates..."):
    try:
      response = requests.get(
        f"{API_BASE_URL}/api/jobs/{job_id}/candidates",
        headers=auth_headers(),
        timeout=30,
      )
    except requests.exceptions.ConnectionError:
      raise ValueError(
        "Backend is not running. Start it with: "
        "uvicorn backend.main:app --reload --port 8000"
      )
  if not response.ok:
    raise ValueError(response_detail(response))
  candidates = response.json()
  return sorted(
    candidates,
    key=lambda candidate: candidate.get("match_score") or -1,
    reverse=True,
  )


def show_request_error(exc: Exception) -> None:
  if isinstance(exc, requests.exceptions.ConnectionError):
    st.error(
      "Backend is not running. Start it with: "
      "uvicorn backend.main:app --reload --port 8000"
    )
    return
  if isinstance(exc, requests.RequestException):
    st.error(
      "Could not reach the FastAPI backend. Check that it is running and "
      f"available at {API_BASE_URL}."
    )
  else:
    st.error(str(exc))


st.title("Candidate Results")
st.caption("Review transparent AI matching results before making a human decision.")
st.warning("Recruiter review required")

if saved_decision := st.session_state.pop("saved_decision", None):
  st.success(saved_decision)

selected_job = select_saved_job(
  API_BASE_URL,
  auth_headers(),
  "results_job_title",
)
load = st.button("Load candidates", type="primary", disabled=selected_job is None)

if load:
  try:
    job_id = selected_job["job_id"]
    st.session_state["results_job_id"] = job_id
    st.session_state["candidate_results"] = load_candidates(job_id)
    st.session_state.pop("selected_candidate_id", None)
  except (requests.RequestException, ValueError) as exc:
    st.session_state["candidate_results"] = []
    show_request_error(exc)

candidates = st.session_state.get("candidate_results", [])
if not candidates:
  if st.session_state.get("results_job_id") and not load:
    st.info("No candidates were found for this job.")
  st.stop()

st.subheader("Ranked candidates")
summary_rows = [
  {
    "Candidate": candidate["candidate_id"],
    "Score": candidate.get("match_score"),
    "Recommendation": candidate.get("recommendation", ""),
    "Risk flags": ", ".join(candidate.get("risk_flag_codes", [])) or "None",
    "Status": candidate.get("status", ""),
  }
  for candidate in candidates
]
st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
st.download_button(
  "Download comparison CSV",
  pd.DataFrame(summary_rows).to_csv(index=False).encode("utf-8"),
  file_name="hirewise_candidate_comparison.csv",
  mime="text/csv",
)

comparison_ids = st.multiselect(
  "Compare candidates",
  [candidate["candidate_id"] for candidate in candidates],
  max_selections=2,
)
if len(comparison_ids) == 2:
  compared = [next(item for item in candidates if item["candidate_id"] == cid) for cid in comparison_ids]
  st.markdown("#### Candidate comparison")
  st.dataframe(
    pd.DataFrame([
      {"Metric": "Score", compared[0]["candidate_id"]: compared[0].get("match_score"), compared[1]["candidate_id"]: compared[1].get("match_score")},
      {"Metric": "Extraction confidence", compared[0]["candidate_id"]: compared[0].get("extraction_confidence"), compared[1]["candidate_id"]: compared[1].get("extraction_confidence")},
      {"Metric": "Risk flags", compared[0]["candidate_id"]: ", ".join(compared[0].get("risk_flag_codes", [])) or "None", compared[1]["candidate_id"]: ", ".join(compared[1].get("risk_flag_codes", [])) or "None"},
    ]),
    use_container_width=True,
    hide_index=True,
  )

candidate_ids = [candidate["candidate_id"] for candidate in candidates]
default_candidate = st.session_state.get("selected_candidate_id", candidate_ids[0])
selected_candidate_id = st.selectbox(
  "Candidate to review",
  candidate_ids,
  index=candidate_ids.index(default_candidate) if default_candidate in candidate_ids else 0,
  key="selected_candidate_id",
)

try:
  with st.spinner("Loading candidate details..."):
    detail_response = requests.get(
      f"{API_BASE_URL}/api/candidates/{selected_candidate_id}",
      headers=auth_headers(),
      timeout=30,
    )
  if not detail_response.ok:
    st.error(response_detail(detail_response))
    st.stop()
  detail = detail_response.json()
except requests.RequestException as exc:
  show_request_error(exc)
  st.stop()

st.download_button(
  "Download candidate explanation PDF",
  candidate_pdf(selected_candidate_id, detail),
  file_name=f"{selected_candidate_id}_explanation.pdf",
  mime="application/pdf",
)

match = detail.get("match", {})
review = detail.get("review", {})
summary = detail.get("summary", {})

st.subheader(f"Review: {selected_candidate_id}")
left, right = st.columns(2)
score = match.get("match_score")
match_available = match.get("match_status") != "unavailable" and score is not None
left.metric(
  "Overall score",
  f"{score:.1f}" if match_available else "Not available",
)
right.write("**Recommendation**")
right.write(summary.get("recommendation", "No recommendation provided."))

confidence_left, confidence_right = st.columns(2)
confidence_left.metric("Extraction confidence", f"{summary.get('extraction_confidence', 0):.0%}")
confidence_right.metric("Matching confidence", f"{review.get('matching_confidence', 0):.0%}")
if not match_available:
  st.error("No reliable match score was produced. Check the job requirements and CV extraction.")
elif summary.get("extraction_confidence", 0) < 0.75:
  st.warning("Low extraction confidence. Review the original CV before relying on this result.")
if review.get("human_review_required", True):
  st.info("Recruiter review required. The AI does not make the final hiring decision.")

st.markdown("#### Score breakdown")
breakdown = match.get("score_breakdown", {})
st.dataframe(
  pd.DataFrame(
    [
      {"Component": name.replace("_", " ").title(), "Score": score}
      for name, score in breakdown.items()
    ]
  ),
  use_container_width=True,
  hide_index=True,
)

matched_skills = match.get("matched_mandatory_skills", []) + match.get(
  "matched_preferred_skills", []
)
missing_skills = [gap.get("skill", "") for gap in match.get("skill_gaps", [])]
skill_left, skill_right = st.columns(2)
skill_left.write("**Matched skills**")
skill_left.write(", ".join(matched_skills) or "None recorded")
skill_right.write("**Missing skills**")
skill_right.write(", ".join(missing_skills) or "None recorded")

uncertain_matches = match.get("uncertain_matches", [])
st.write("**Uncertain matches**")
if uncertain_matches:
  st.dataframe(
    pd.DataFrame(
      [
        {
          "Requirement": item.get("requirement", ""),
          "Reason": item.get("reason", ""),
        }
        for item in uncertain_matches
      ]
    ),
    use_container_width=True,
    hide_index=True,
  )
else:
  st.write("None recorded")

st.write("**Explanation**")
method = review.get("explanation_method", "rule_template")
st.caption("Explanation source: " + ("Gemini LLM rewrite" if method == "llm_reworded" else "Deterministic fallback"))
st.write(review.get("explanation", "No explanation provided.").split("Points for the recruiter to check:")[0].strip())

st.write("**Recommended recruiter checks**")
checks = []
if not match_available:
  checks.append("Add clear mandatory or preferred requirements to the job description.")
if summary.get("extraction_confidence", 0) < 0.75:
  checks.append("Verify the CV text, experience dates, and education manually.")
checks.extend(flag.get("message", "Review the flagged issue.") for flag in review.get("risk_flags", []))
for check in dict.fromkeys(checks):
  st.warning(check)

privacy = review.get("privacy_check", {})
st.write("**Privacy check**")
if privacy.get("passed"):
  st.success("Passed")
else:
  st.error("Privacy check requires attention")
  st.write(", ".join(privacy.get("violations", [])) or "No violation details provided.")

risk_flags = review.get("risk_flags", [])
st.write("**Risk flags**")
if risk_flags:
  for flag in risk_flags:
    st.warning(f"{flag.get('code', 'Risk flag')}: {flag.get('message', '')}")
else:
  st.write("None recorded")

st.markdown("#### Human decision")
with st.form("human_decision_form"):
  decision = st.radio(
    "Decision",
    options=["shortlist", "hold", "not_selected"],
    format_func=lambda value: {
      "shortlist": "Shortlist",
      "hold": "Hold",
      "not_selected": "Not Selected",
    }[value],
    horizontal=True,
  )
  note = st.text_area("Note (optional)", max_chars=2000)
  save_decision = st.form_submit_button("Save decision", type="primary")

if save_decision:
  try:
    with st.spinner("Saving human decision..."):
      decision_response = requests.post(
        f"{API_BASE_URL}/api/candidates/{selected_candidate_id}/decision",
        json={"decision": decision, "note": note},
        headers=auth_headers(),
        timeout=30,
      )
    if not decision_response.ok:
      st.error(response_detail(decision_response))
    else:
      st.session_state["candidate_results"] = load_candidates(
        st.session_state["results_job_id"]
      )
      st.session_state["saved_decision"] = (
        f"Human decision saved: {decision.replace('_', ' ').title()}."
      )
      st.rerun()
  except (requests.RequestException, ValueError) as exc:
    show_request_error(exc)