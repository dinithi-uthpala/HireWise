"""Skill taxonomy: canonical skill names + synonym expansion.

Used by:
  - Agent 1 -> to *extract* technical/soft skills from a CV.
  - Agent 2 -> to *normalize* skill names ("MS Excel" -> "Excel",
               "Structured Query Language" -> "SQL", "PowerBI" -> "Power BI")
               and to do taxonomy/semantic matching instead of naive
               exact-keyword matching.

The same table is seeded into the ChromaDB knowledge base so the Information
Retrieval module can retrieve it at match time.
"""
from __future__ import annotations

import re

# canonical skill -> accepted surface forms (lower-case)
SKILL_SYNONYMS: dict[str, set[str]] = {
    # --- programming / query languages --------------------------------------
    "Python": {"python", "python3", "python 3", "py"},
    "SQL": {"sql", "structured query language", "mysql", "postgresql", "postgres",
            "pl/sql", "tsql", "t-sql", "ms sql server", "mssql", "sqlite", "pyspark sql"},
    "R": {"r", "r language", "r programming"},
    "Java": {"java", "java 11", "java 17"},
    "JavaScript": {"javascript", "js", "ecmascript", "typescript"},
    "C++": {"c++", "cpp", "c plus plus"},
    "C#": {"c#", "c sharp", "dotnet", ".net", "csharp"},
    "Go": {"go", "golang"},
    "Scala": {"scala"},
    # --- data analysis / BI ----------------------------------------------------
    "Excel": {"excel", "ms excel", "microsoft excel", "advanced excel",
              "spreadsheets", "spreadsheet", "pivot tables"},
    "Power BI": {"power bi", "powerbi", "power bi desktop", "power bi service", "pbi"},
    "Tableau": {"tableau", "tableau desktop", "tableau public"},
    "Looker Studio": {"looker studio", "looker", "google data studio", "data studio"},
    "Google Sheets": {"google sheets", "g sheets"},
    "Statistics": {"statistics", "statistical analysis", "inferential statistics",
                   "descriptive statistics", "hypothesis testing", "a/b testing",
                   "experimental design"},
    "Data Visualization": {"data visualization", "data visualisation", "visualization",
                           "visualisation", "dashboards", "dashboarding", "charts",
                           "data storytelling"},
    "Data Cleaning": {"data cleaning", "data wrangling", "data preparation",
                      "data munging", "data cleansing", "standardizing data"},
    "ETL": {"etl", "extract transform load", "data pipelines", "pipelines"},
# --- machine learning / AI --------------------------------------------------
    "Machine Learning": {"machine learning", "ml", "supervised learning",
                         "unsupervised learning", "regression", "classification",
                         "clustering"},
    "Deep Learning": {"deep learning", "dl", "neural networks", "neural network",
                      "cnn", "rnn", "transformers"},
    "NLP": {"nlp", "natural language processing"},
    "scikit-learn": {"scikit-learn", "sklearn", "scikit learn"},
    "PyTorch": {"pytorch", "torch"},
    "TensorFlow": {"tensorflow", "tf", "keras"},
    "Pandas": {"pandas", "pandas library"},
    "NumPy": {"numpy", "numpy library"},
    # --- data engineering ----------------------------------------------------------
    "Snowflake": {"snowflake", "snowflake warehouse"},
    "dbt": {"dbt", "data build tool"},
    "Airflow": {"airflow", "apache airflow"},
    "Spark": {"spark", "apache spark", "pyspark", "spark sql"},
    "Kafka": {"kafka", "apache kafka"},
    # --- databases --------------------------------------------------------------------
    "PostgreSQL": {"postgres", "postgresql", "psql"},
    "MongoDB": {"mongodb", "mongo", "mongo db", "nosql"},
    "BigQuery": {"bigquery", "google bigquery"},
    # --- soft skills --------------------------------------------------------------------
    "Communication": {"communication", "written communication", "verbal communication",
                      "presentation skills", "public speaking"},
    "Teamwork": {"teamwork", "collaboration", "collaborative", "team player"},
    "Problem Solving": {"problem solving", "analytical thinking", "critical thinking",
                        "critical analysis"},
    "Time Management": {"time management", "prioritisation", "prioritization", "organisation",
                        "organization", "organizational"},
    "Attention to Detail": {"attention to detail", "detail oriented", "detail-oriented"},
    "Adaptability": {"adaptability", "flexibility", "quick learner", "fast learner"},
    "Leadership": {"leadership", "leading teams", "team lead", "mentoring"},
    "Agile": {"agile", "scrum", "kanban", "sprint planning"},
}

# SQL Server synonyms kept separate for readability.
SKILL_SYNONYMS["SQL Server"] = {"sql server", "ms sql server", "tsql"}

_CACHE: dict[str, str] = {}


def _compact(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token)


def normalize_skill(name: str) -> str:
    """Return the canonical skill name for a given surface form.

    Falls back to the trimmed original if the name is unknown.
    """
    key = name.strip().lower()
    if not key:
        return name.strip()
    if key in _CACHE:
        return _CACHE[key]
    for canonical, forms in SKILL_SYNONYMS.items():
        if key in forms or any(_compact(key) == _compact(form) for form in forms):
            _CACHE[key] = canonical
            return canonical
    _CACHE[key] = name.strip()
    return name.strip()


def all_canonical_skills() -> list[str]:
    """All canonical skill names (sorted)."""
    return sorted(SKILL_SYNONYMS.keys())


def find_skills_in_text(text: str) -> list[str]:
    """Return the canonical skills found anywhere in ``text`` (Agent 1)."""
    lowered = text.lower()
    found: set[str] = set()
    for canonical, forms in SKILL_SYNONYMS.items():
        if any(form in lowered for form in forms):
            found.add(canonical)
    return sorted(found)


def find_soft_skills_in_text(text: str) -> list[str]:
    """Return soft skills found in ``text``."""
    return [s for s in ("Communication", "Teamwork", "Problem Solving", "Time Management",
                        "Attention to Detail", "Adaptability", "Leadership", "Agile")
            if s.lower() in text.lower()]