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
score = match.get("match_score")
match_available = match.get("match_status") != "unavailable" and score is not None

score_color = "green" if match_available and score >= 80 else "yellow" if match_available and score >= 60 else "orange" if match_available and score < 60 else "gray"
score_value = f"{score:.1f}" if match_available else "N/A"

left, right = st.columns(2)
with left:
  st.markdown("**Overall score**")
  st.badge(score_value, color=score_color)
with right:
  st.markdown("**Recommendation**")
  st.write(summary.get("recommendation", "No recommendation provided."))

privacy = review.get("privacy_check", {})
st.write("**Privacy check**")
if privacy.get("passed"):
  st.success("Passed")
else:
  st.error("Privacy check requires attention")
  st.write(", ".join(privacy.get("violations", [])) or "No violation details provided.")

if not match_available:
  st.error("No reliable match score was produced. Check the job requirements and CV extraction.")
if review.get("human_review_required", True):
  st.info("Recruiter review required. The AI does not make the final hiring decision.")

breakdown = match.get("score_breakdown", {})
if breakdown:
  with st.expander("Score breakdown", expanded=False):
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

matched_skills = match.get("matched_mandatory_skills", []) + match.get("matched_preferred_skills", [])
missing_skills = [gap.get("skill", "") for gap in match.get("skill_gaps", []) if gap.get("skill")]
if matched_skills or missing_skills:
  with st.expander("Matched / missing skills", expanded=False):
    cols = st.columns(2)
    if matched_skills:
      with cols[0]:
        st.write("**Matched skills**")
        st.write(", ".join(matched_skills))
    if missing_skills:
      with cols[1]:
        st.write("**Missing skills**")
        st.write(", ".join(missing_skills))

uncertain_matches = match.get("uncertain_matches", [])
if uncertain_matches:
  with st.expander("Uncertain matches", expanded=False):
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

explanation = review.get("explanation", "")
if explanation:
  with st.expander("Explanation", expanded=False):
    method = review.get("explanation_method", "rule_template")
    st.caption("Explanation source: " + ("Gemini LLM rewrite" if method == "llm_reworded" else "Deterministic fallback"))
    st.write(explanation.strip())

risk_flags = review.get("risk_flags", [])
if risk_flags:
  with st.expander("Risk flags", expanded=False):
    cols = st.columns(min(len(risk_flags), 3))
    for index, flag in enumerate(risk_flags):
      code = flag.get("code", "RISK_FLAG")
      severity = str(flag.get("severity", "warning")).lower()
      if severity in {"critical", "high"}:
        color = "red"
      elif severity in {"medium", "warning", "moderate"}:
        color = "orange"
      elif severity in {"low", "info"}:
        color = "yellow"
      else:
        color = "gray"
      with cols[index % min(len(risk_flags), 3)]:
        st.badge(code, color=color)

st.divider()
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
      st.success(st.session_state["saved_decision"])
      st.divider()
      st.page_link("pages/5_Candidate_Detail.py", label="➡️ View Candidate Detail")
  except (requests.RequestException, ValueError) as exc:
    show_request_error(exc)