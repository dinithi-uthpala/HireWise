"""Page 3 - Candidate Intelligence Agent upload workspace."""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

st.title("Candidate Intelligence")
st.caption("Upload CVs to extract an anonymous, job-relevant profile.")

files = st.file_uploader(
    "Choose CV files",
    type=["pdf", "docx", "txt", "md"],
    accept_multiple_files=True,
    help="Files are validated, PII-redacted, parsed, and encrypted by Agent 1.",
)

uploaded_files = files or []

if st.button("Process CVs", type="primary", disabled=not uploaded_files):
    payload = [
        ("files", (file.name, file.getvalue(), file.type or "application/octet-stream"))
        for file in uploaded_files
    ]
    with st.spinner("Agent 1 is extracting and anonymizing candidate profiles..."):
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/agent1/process-batch",
                files=payload,
                timeout=120,
            )
        except requests.RequestException as exc:
            st.error(f"Could not reach the FastAPI backend: {exc}")
        else:
            if response.ok:
                results = response.json()
                st.session_state["agent1_results"] = results
                st.success(f"Processed {len(results)} candidate(s).")
            else:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                st.error(f"Agent 1 rejected the upload: {detail}")

results = st.session_state.get("agent1_results", [])
if results:
    st.subheader("Agent activity")
    activity = st.columns(3)
    activity[0].success("Agent 1\n\nCV extracted")
    activity[1].success("Privacy boundary\n\nPII redacted")
    activity[2].success("Profile ready\n\nAnonymous output")

    rows = []
    for result in results:
        profile = result["profile"]
        rows.append(
            {
                "Candidate": result["candidate_id"],
                "Status": result["parse_status"].replace("_", " ").title(),
                "Confidence": f"{result['extraction_confidence']:.0%}",
                "Technical skills": ", ".join(profile["technical_skills"]) or "None detected",
                "PII removed": result["pii"]["detected_count"],
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    for result in results:
        with st.expander(f"{result['candidate_id']} | {result['parse_status'].replace('_', ' ').title()}"):
            profile = result["profile"]
            left, right = st.columns(2)
            left.metric("Extraction confidence", f"{result['extraction_confidence']:.0%}")
            right.metric("Personal identifiers redacted", result["pii"]["detected_count"])
            st.write("**Skills**", ", ".join(profile["technical_skills"]) or "None detected")
            st.write("**Experience**", f"{profile['total_experience_years']:.1f} years")
            st.write("**Education**", ", ".join(item["degree"] for item in profile["education"]) or "None detected")
            if result["warnings"]:
                for warning in result["warnings"]:
                    st.warning(warning)
            with st.expander("Privacy report"):
                st.write(", ".join(item["type"].replace("_", " ").title() for item in result["pii"]["items"]) or "No identifiers detected")
                st.code(result["pii"]["redacted_text"], language="text")