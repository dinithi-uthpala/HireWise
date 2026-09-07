"""Agent 2 - Job Matching & Retrieval Agent.

Determines how well an anonymized profile matches a vacancy using approved,
predefined, job-related criteria. Responsibilities:
    - extract job requirements (mandatory / preferred skills, experience)
    - retrieval from the ChromaDB knowledge base (competency frameworks,
      skill taxonomy, scoring rubric)
    - skill normalization + taxonomy/semantic matching
    - transparent, fixed scoring (weighted rubric from config)
    - evidence for every score component + skill-gap analysis

Input : anonymous CandidateProfile + job description
Output: MatchResultData (score, evidence, gaps, retrieved documents)
"""

# TODO(Team member 2): implement vector retrieval, matching and scoring.