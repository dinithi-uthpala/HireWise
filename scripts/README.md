# Scripts

Utility scripts for setup and demos.

| Script | Purpose |
| --- | --- |
| `install_local.py` | optional: installs backend + frontend + (optionally) LLM requirements |
| `seed_knowledge_base.py` | loads `knowledge_base/docs/` into the ChromaDB vector store |
| `generate_sample_cvs.py` | creates sample CVs (PDF/DOCX) in `samples/cvs/` |
| `run_all.py` | convenience: starts FastAPI backend + Streamlit frontend |

Run the knowledge-base seed script from the repository root after installing
`requirements-backend.txt`:

	python scripts/seed_knowledge_base.py

The Agent 2 pipeline retrieves approved guidance and compact source evidence
before deterministic scoring. Retrieval never calculates or changes the
numeric match score.