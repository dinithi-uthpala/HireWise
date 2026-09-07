# Knowledge Base Documents

Seed documents that Agent 2 retrieves from the ChromaDB vector store
at match time. Store them as Markdown files here and load them with
`scripts/seed_kb.py`.

Planned documents (10-20 records):
  - `data_analyst_competency_framework.md`
  - `software_engineer_competency_framework.md`
  - `hr_assistant_competency_framework.md`
  - `skill_taxonomy.md` (canonical skills + synonyms)
  - `scoring_rubric.md` (fixed weighted formula, thresholds)
  - `mandatory_vs_preferred.md` (definitions + guidelines)
  - `recruitment_evaluation_policy.md`
  - `retrieval_evidence_rules.md`

Each file should carry front-matter metadata (id, category) used for
filtered retrieval.