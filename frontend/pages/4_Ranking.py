"""Candidate results and recruiter review."""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def response_detail(response: requests.Response) -> str:
  """Return the backend's useful error text when available."""
  try:
    body = response.json()
  except ValueError:
    return response.text or f"Request failed with status {response.status_code}."
  return str(body.get("detail", body))


def load_candidates(job_id: str) -> list[dict]:
  response = requests.get(
    f"{API_BASE_URL}/api/jobs/{job_id}/candidates", timeout=30
  )
  if response.status_code == 404:
    raise ValueError("That job was not found.")
  if response.status_code == 422:
    raise ValueError(response_detail(response))
  response.raise_for_status()
  candidates = response.json()
  return sorted(
    candidates,
    key=lambda candidate: candidate.get("match_score") or -1,
    reverse=True,
  )


def show_request_error(exc: Exception) -> None:
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

with st.form("load_candidates_form"):
  job_id = st.text_input("Job ID", value=st.session_state.get("results_job_id", ""))
  load = st.form_submit_button("Load candidates", type="primary")

if load:
  job_id = job_id.strip()
  if not job_id:
    st.error("Enter a job ID to load candidate results.")
  else:
    try:
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

candidate_ids = [candidate["candidate_id"] for candidate in candidates]
default_candidate = st.session_state.get("selected_candidate_id", candidate_ids[0])
selected_candidate_id = st.selectbox(
  "Candidate to review",
  candidate_ids,
  index=candidate_ids.index(default_candidate) if default_candidate in candidate_ids else 0,
  key="selected_candidate_id",
)

try:
  detail_response = requests.get(
    f"{API_BASE_URL}/api/candidates/{selected_candidate_id}", timeout=30
  )
  if detail_response.status_code == 404:
    st.error("That candidate could not be found. Reload the job results.")
    st.stop()
  if detail_response.status_code == 422:
    st.error(response_detail(detail_response))
    st.stop()
  detail_response.raise_for_status()
  detail = detail_response.json()
except requests.RequestException as exc:
  show_request_error(exc)
  st.stop()

match = detail.get("match", {})
review = detail.get("review", {})
summary = detail.get("summary", {})

st.subheader(f"Review: {selected_candidate_id}")
left, right = st.columns(2)
left.metric(
  "Overall score",
  "Not available" if match.get("match_score") is None else f"{match['match_score']:.1f}",
)
right.write("**Recommendation**")
right.write(summary.get("recommendation", "No recommendation provided."))

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
st.write(review.get("explanation", "No explanation provided."))

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
    decision_response = requests.post(
      f"{API_BASE_URL}/api/candidates/{selected_candidate_id}/decision",
      json={"decision": decision, "note": note},
      timeout=30,
    )
    if decision_response.status_code == 404:
      st.error(response_detail(decision_response))
    elif decision_response.status_code == 422:
      st.error(response_detail(decision_response))
    else:
      decision_response.raise_for_status()
      st.session_state["candidate_results"] = load_candidates(
        st.session_state["results_job_id"]
      )
      st.session_state["saved_decision"] = (
        f"Human decision saved: {decision.replace('_', ' ').title()}."
      )
      st.rerun()
  except (requests.RequestException, ValueError) as exc:
    show_request_error(exc)