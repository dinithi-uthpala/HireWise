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
            "pl/sql", "mssql", "sqlite", "pyspark sql"},
    "R": {"r", "r language", "r programming"},
    "Java": {"java", "java 11", "java 17"},
    "JavaScript": {"javascript", "js", "ecmascript", "typescript"},
    "C++": {"c++", "cpp", "c plus plus"},
    "C#": {"c#", "c sharp", "dotnet", ".net", "csharp"},
    "Go": {"go", "golang"},
    "Scala": {"scala"},
    "HTML": {"html", "html5"},
    "CSS": {"css", "css3"},
    "React": {"react", "reactjs", "react.js"},
    "TypeScript": {"typescript", "ts"},
    "REST APIs": {"rest api", "rest apis", "restful api", "web api"},
    "FastAPI": {"fastapi", "fast api"},
    "Flask": {"flask"},
    "Spring Boot": {"spring boot"},
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
    "Data Analysis": {"data analysis", "data analytics", "analytical analysis"},
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
    # --- platform, testing, and IT operations --------------------------------
    "Docker": {"docker", "containers", "containerization", "containerisation"},
    "AWS": {"aws", "amazon web services"},
    "Cloud": {"cloud", "cloud computing", "cloud services"},
    "Kubernetes": {"kubernetes", "k8s"},
    "Terraform": {"terraform", "infrastructure as code"},
    "Linux": {"linux", "ubuntu", "unix"},
    "Windows": {"windows", "windows server"},
    "CI/CD": {"ci/cd", "continuous integration", "continuous delivery", "continuous deployment"},
    "Git": {"git", "github", "gitlab", "version control"},
    "Software Testing": {"software testing", "software test", "quality assurance", "qa"},
    "Test Automation": {"test automation", "automated testing", "automation testing"},
    "Selenium": {"selenium"},
    "Pytest": {"pytest", "py.test"},
    "API Testing": {"api testing", "api test"},
    "Troubleshooting": {"troubleshooting", "troubleshoot", "technical support"},
    "Networking": {"networking", "computer networks", "tcp/ip", "dns"},
    "Cybersecurity": {"cybersecurity", "cyber security", "information security"},
    "Customer Support": {"customer support", "user support", "customer service"},
    "Tailwind": {"tailwind", "tailwind css"},
    "Bootstrap": {"bootstrap"},
    "Material UI": {"material ui", "mui"},
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
SKILL_SYNONYMS["SQL Server"] = {"sql server", "ms sql server", "tsql", "t-sql"}

# Retrieval-backed conceptual relationships. These are intentionally narrower
# than synonyms: a related skill may support a broader capability, but it is
# not treated as an exact synonym unless an approved retrieved document also
# contains the relationship.
RELATED_SKILLS: dict[str, set[str]] = {
    "Data Visualization": {"Power BI", "Tableau", "Looker Studio"},
}

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
    """Return the canonical skills found anywhere in ``text`` (Agent 1).

    Uses word-boundary matching so a single-letter skill such as "R" cannot
    false-match inside words like "Structured".
    """
    lowered = text.lower()
    matches: list[tuple[int, int, str]] = []
    for canonical, forms in SKILL_SYNONYMS.items():
        for form in forms:
            for match in re.finditer(
                rf"(?<![a-z0-9]){re.escape(form)}(?![a-z0-9])", lowered
            ):
                matches.append((match.start(), match.end(), canonical))

    selected: list[tuple[int, int, str]] = []
    for start, end, canonical in sorted(
        matches,
        key=lambda item: (-(item[1] - item[0]), item[0], item[2]),
    ):
        if any(start < selected_end and selected_start < end
               for selected_start, selected_end, _ in selected):
            continue
        selected.append((start, end, canonical))

    return sorted({canonical for _, _, canonical in selected})


def find_soft_skills_in_text(text: str) -> list[str]:
    """Return soft skills found in ``text``."""
    return [s for s in ("Communication", "Teamwork", "Problem Solving", "Time Management",
                        "Attention to Detail", "Adaptability", "Leadership", "Agile")
            if s.lower() in text.lower()]