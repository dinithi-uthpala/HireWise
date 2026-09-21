"""Agent 2 retrieval adapter for approved job-role guidance."""
from __future__ import annotations

from backend.ir.skill_taxonomy import RELATED_SKILLS, find_skills_in_text
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


def _related_skills_from_document(
    job: JobRequirement,
    document_content: str,
) -> list[str]:
    """Return approved related skills explicitly supported by one KB document."""
    document_skills = set(find_skills_in_text(document_content))
    related: set[str] = set()
    required_skills = [*job.mandatory_skills, *job.preferred_skills]

    for required_skill in required_skills:
        if required_skill not in document_skills:
            continue
        for related_skill in RELATED_SKILLS.get(required_skill, set()):
            if related_skill in document_skills:
                related.add(related_skill)
    return sorted(related)


def retrieve_job_evidence(
    job: JobRequirement,
    top_k: int = 3,
) -> tuple[list[RetrievalEvidence], list[str]]:
    """Retrieve compact source evidence and approved related-skill context."""
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
            related_skills=_related_skills_from_document(job, document.content),
        )
        for document in documents
    ]
    if not evidence:
        return [], ["No approved knowledge-base evidence was retrieved."]
    return evidence, []
