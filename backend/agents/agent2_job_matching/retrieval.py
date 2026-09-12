"""Agent 2 retrieval adapter for approved job-role guidance."""
from __future__ import annotations

from backend.ir.vector_store import retrieve_relevant_criteria
from backend.schemas import JobRequirement, RetrievalEvidence


def build_retrieval_query(job: JobRequirement) -> str:
    """Build a deterministic query from normalized job requirements only."""
    parts = [job.title.strip()]
    parts.extend(job.mandatory_skills)
    parts.extend(job.preferred_skills)
    if job.minimum_experience_years > 0:
        parts.append(f"{job.minimum_experience_years:g} years experience")
    if job.required_education_level.strip():
        parts.append(job.required_education_level.strip())
    return " ".join(part for part in parts if part).strip()


def retrieve_job_evidence(
    job: JobRequirement,
    top_k: int = 3,
) -> tuple[list[RetrievalEvidence], list[str]]:
    """Retrieve compact source evidence without exposing document contents."""
    query = build_retrieval_query(job)
    if not query:
        return [], ["No measurable job requirements were available for retrieval."]

    try:
        documents = retrieve_relevant_criteria(query, top_k=top_k)
    except Exception:
        return [], [
            "Knowledge-base retrieval was unavailable; deterministic scoring continued."
        ]

    evidence = [
        RetrievalEvidence(
            source=document.source,
            category=document.category,
            relevance=document.relevance,
        )
        for document in documents
    ]
    if not evidence:
        return [], ["No approved knowledge-base evidence was retrieved."]
    return evidence, []
