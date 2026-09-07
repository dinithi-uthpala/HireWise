"""HireWise Recruiter Dashboard - Streamlit entry point.

Run with:
    cd frontend
    streamlit run app.py

The app is a small internal HR dashboard for the multi-agent demo:
    Login -> Create Job -> Upload CVs -> Agent pipeline ->
    Candidate Ranking -> Candidate Detail (evidence, gaps, confidence) ->
    Human Decision -> Audit trail.

Uses Streamlit's native multipage layout: extra screens live in `pages/`.
The frontend calls the FastAPI backend (`API_BASE_URL` from `.env`).
"""

# TODO(Team): add login, job creation, CV upload + agent pipeline UI here.