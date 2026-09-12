"""Agent 2 - Job Matching & Retrieval Agent.

The package extracts job requirements, retrieves approved role guidance from
the ChromaDB knowledge base, and compares an anonymous CandidateProfile with
the vacancy using deterministic scoring. Retrieval supplies context and
source evidence; it never calculates or changes the numeric match score.

Input : anonymous CandidateProfile + job description
Output: MatchResult (score, component evidence, gaps, and retrieval sources)
"""