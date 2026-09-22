# HireWise

**A Responsible Multi-Agent AI System for Explainable Candidate Shortlisting**
*Information Retrieval and Web Analytics (IT3041) —  Group Assignment*

## One-line description

HireWise helps HR officers conduct faster, consistent, transparent and
privacy-aware **first-stage candidate shortlisting** from CVs. It is a
**decision-support** system: the AI recommends, the human decides.

## Architecture (3 collaborating agents)

```
        HR Dashboard (Streamlit frontend)
                   │  Job + CVs (REST / JSON, JWT)
                   ▼
   ┌────────────────────────────────────────┐
   │ Agent 1  Candidate Intelligence Agent   │  CV → anonymous structured profile
   │          (extraction + PII redaction)   │  + extraction confidence
   └───────────────────┬────────────────────┘
                       │  anonymous profile
                       ▼
   ┌────────────────────────────────────────┐
   │ Agent 2  Job Matching & Retrieval Agent │  ChromaDB retrieval, skill
   │          (IR + normalization +   )      │  normalization, transparent score
   └───────────────────┬────────────────────┘
                       │  score + evidence
                       ▼
   ┌────────────────────────────────────────┐
   │ Agent 3  Responsible Decision Agent     │  fairness/privacy/confidence
   │          (explanation + recommendation) │  checks, audit trail
   └───────────────────┬────────────────────┘
                       │  recommendation + risks
                       ▼
                HUMAN HR REVIEW  (final decision)
```

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | FastAPI + SQLModel (SQLite default, PostgreSQL-ready) |
| Frontend | Streamlit (small internal HR dashboard) |
| IR module | ChromaDB vector store (competency frameworks, rubric, skill taxonomy) |
| NLP | spaCy NER + regex + optional LLM (Gemini / OpenAI / Ollama) |
| Security | JWT + RBAC, bcrypt, Fernet CV encryption, upload validation, sanitization |
| Contract | Pydantic-validated JSON over REST (agent communication protocol) |

## Repository layout

```
backend/                     FastAPI backend package
  agents/agent1_candidate_intelligence/   (team member 1)
  agents/agent2_job_matching/             (team member 2)
  agents/agent3_responsible_decision/     (team member 3)
  api/            REST routes (auth, jobs, candidates, decisions, audit, fairness)
  ir/             ChromaDB + skill taxonomy
  security/       JWT / RBAC / PII / encryption / sanitization
frontend/                  Streamlit dashboard (pages/ per screen)
knowledge_base/docs/       seed documents loaded into ChromaDB
samples/cvs/               demo CVs (PDF/DOCX)
scripts/                   seed_kb.py, generate_sample_cvs.py, run_all.py
tests/                     pytest suite
data/  storage/  chroma_db/   runtime artifacts (git-ignored)
```

## Setup (first time)

```bash
# 1. Create a virtual environment (from the repo root)
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell

# 2. Install dependencies
py -m pip install -r requirements-backend.txt
py -m pip install -r requirements-frontend.txt

# (optional) LLM integration  -- pip install -r requirements-llm.txt

# 3. Configure environment
copy .env.example .env            # Windows  (cp .env.example .env on Linux/mac)

# 4. Seed the vector knowledge base (after implementing scripts/seed_kb.py)
py scripts/seed_kb.py

# 5. Run the backend (FastAPI)
uvicorn backend.main:app --reload --port 8000
#    API docs:  http://127.0.0.1:8000/docs

# 6. Run the frontend (Streamlit) -- second terminal
cd frontend
streamlit run app.py
#    Dashboard:  http://localhost:8501
```

Default login (auto-seeded admin): `admin` / `admin123` — change in `.env`.

## Assignment coverage map

- ✅ At least two interacting intelligent agents (we have three)
- ✅ LLM + NLP (NER/extraction) — with deterministic fallback so it runs offline
- ✅ Information Retrieval module (ChromaDB retrieval used for matching evidence)
- ✅ Security (authentication, RBAC, file validation, encryption, sanitization)
- ✅ Defined agent communication protocol (REST + JSON, Pydantic-validated)
- ✅ Responsible AI (fairness check, explainability, transparency, PII protection,
  human review, audit trail, human override; AI never makes the final decision)
- ✅ Commercialization strategy (report/viva deliverable — see docs)

## Work division (3 branches)

| Area | Owner suggestion |
| --- | --- |
| Agent 1 (Candidate Intelligence) | team member 1 |
| Agent 2 (Job Matching & Retrieval) | team member 2 |
| Agent 3 (Responsible Decision) + dashboard glue | team member 3 |

Each member works on their own branch and merges into `main`.
