# Knowledge Base Documents

Approved, fictional project-knowledge documents that Agent 2 can retrieve
from the persistent ChromaDB vector store. Seed them from the repository root
with:

  python scripts/seed_knowledge_base.py

Current document groups include:
  - `data_analyst_competency_framework.md`
  - `software_engineer_competency_framework.md`
  - `hr_assistant_competency_framework.md`
  - `skill_taxonomy.md` (canonical skills + synonyms)
  - `recruitment_scoring_guidelines.md` (fixed weighted formula)
  - `mandatory_vs_preferred_criteria.md` (definitions + guidelines)
  - `retrieval_evidence_rules.md`
  - `job_responsibility_evaluation_guidance.md`
  - `experience_evaluation_guidelines.md`
  - `certification_evaluation_guidance.md`
  - `job_requirement_evidence_rules.md`

Each file carries simple front-matter metadata (`id`, `category`) used for
source-aware retrieval results. The current corpus contains 11 documents.
Retrieval supplies approved guidance and source evidence; the existing
deterministic Agent 2 scorer remains responsible for numeric match scores.