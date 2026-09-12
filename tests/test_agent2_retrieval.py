"""Offline tests for the Agent 2 knowledge base and retrieval infrastructure."""
from __future__ import annotations

from pathlib import Path

from backend.ir.knowledge_base import seed_knowledge_base
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
