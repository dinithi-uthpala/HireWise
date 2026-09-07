# HireWise Frontend (Streamlit)

Small internal HR recruiter dashboard for the multi-agent demo.

## Run

```bash
cd frontend
py -m pip install -r ../requirements-frontend.txt
streamlit run app.py
```

The dashboard calls the FastAPI backend at `API_BASE_URL` (default
`http://127.0.0.1:8000`, configurable via `.env`).

## Pages

| File | Screen |
| --- | --- |
| `app.py` | entry point |
| `pages/1_Login_Dashboard.py` | login + overview |
| `pages/2_Create_Job.py` | create vacancy + requirement breakdown |
| `pages/3_Upload_CVs.py` | multi-CV upload + live agent activity + PII counter |
| `pages/4_Ranking.py` | transparent candidate ranking & comparison |
| `pages/5_Candidate_Detail.py` | evidence, skill gaps, confidence, risk |
| `pages/6_Decision_Audit.py` | human decision/override + audit timeline |
| `pages/7_Fairness_Test.py` | paired-CV fairness test mode |

Every screen is currently a stub - implementation is split across the team.