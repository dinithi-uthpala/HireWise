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