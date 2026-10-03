"""Offline tests for the Agent 2 knowledge base and retrieval infrastructure."""
from __future__ import annotations

from pathlib import Path

from backend.ir.knowledge_base import load_knowledge_documents, seed_knowledge_base
from backend.ir.vector_store import retrieve_relevant_criteria


DOCS = {
    "data_analyst_competency_framework.md": """---
id: data-analyst-framework
category: competency_framework
---
# Data Analyst Competency Framework

Data analysts commonly use Python, SQL, Pandas, Excel, Power BI, Tableau, and data visualization.
Typical responsibilities include querying databases, cleaning data, and creating dashboards.
""",
    "hr_recruitment_guidance.md": """---
id: hr-recruitment-guidance
category: recruitment_guidance
---
# HR Recruitment Guidance

Recruitment evaluation should use job-related criteria, explain evidence, and preserve human review.
""",
}


def test_knowledge_base_indexes_and_retrieves_role_guidance(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    for filename, content in DOCS.items():
        (docs_dir / filename).write_text(content, encoding="utf-8")

    assert seed_knowledge_base(docs_dir, tmp_path / "chroma") == 2

    results = retrieve_relevant_criteria(
        "Junior Data Analyst Python SQL Power BI",
        top_k=2,
        persist_directory=tmp_path / "chroma",
    )

    assert results
    assert results[0].source == "data_analyst_competency_framework.md"
    assert results[0].category == "competency_framework"
    assert "Python" in results[0].content
    assert results[0].relevance is not None


def test_knowledge_base_retrieves_hr_guidance(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    for filename, content in DOCS.items():
        (docs_dir / filename).write_text(content, encoding="utf-8")

    seed_knowledge_base(docs_dir, tmp_path / "chroma")
    results = retrieve_relevant_criteria(
        "candidate recruitment HR administration",
        top_k=2,
        persist_directory=tmp_path / "chroma",
    )

    assert results
    assert any(result.source == "hr_recruitment_guidance.md" for result in results)


def test_empty_query_returns_no_results(tmp_path: Path) -> None:
    assert retrieve_relevant_criteria("", persist_directory=tmp_path / "chroma") == []


def test_production_knowledge_base_documents_load_with_metadata() -> None:
    documents = load_knowledge_documents()

    assert len(documents) >= 10
    assert all(document.document_id for document in documents)
    assert all(document.source.endswith(".md") for document in documents)
    assert all(document.category for document in documents)
    assert all(document.content.strip() for document in documents)


def test_retrieval_exposes_only_approved_related_skills_from_document(monkeypatch) -> None:
    from backend.agents.agent2_job_matching import retrieval as retrieval_module
    from backend.ir.vector_store import RetrievedDocument
    from backend.schemas import JobRequirement

    document = RetrievedDocument(
        document_id="data-analyst-framework",
        content=(
            "Data Visualization is useful. Power BI, Tableau, and Looker Studio "
            "are common dashboard tools."
        ),
        source="data_analyst_competency_framework.md",
        category="competency_framework",
        distance=0.1,
    )
    monkeypatch.setattr(
        retrieval_module,
        "retrieve_relevant_criteria",
        lambda query, top_k=3: [document],
    )

    job = JobRequirement(
        job_id="JOB-RELATED-002",
        title="Data Analyst",
        mandatory_skills=["Data Visualization"],
    )

    evidence, warnings = retrieval_module.retrieve_job_evidence(job)

    assert warnings == []
    assert evidence[0].related_skills == ["Looker Studio", "Power BI", "Tableau"]
