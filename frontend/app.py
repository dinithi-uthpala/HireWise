"""HireWise Recruiter Dashboard entry point."""
from __future__ import annotations

import os

import streamlit as st

st.set_page_config(page_title="HireWise", page_icon="H", layout="wide")
st.title("HireWise")
st.caption("AI-assisted recruitment workspace")

st.info("Use **Upload CVs** in the sidebar to run Candidate Intelligence Agent 1.")
st.session_state.setdefault("agent1_results", [])
st.metric("Processed candidates", len(st.session_state["agent1_results"]))

if "API_BASE_URL" not in os.environ:
    st.caption("Backend URL: http://127.0.0.1:8000")