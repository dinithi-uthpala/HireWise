"""Built-in job library used by the recruiter workflow."""
from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from backend.models import JobVacancy


@dataclass(frozen=True)
class CatalogJob:
    job_id: str
    title: str
    description: str


CATALOG_JOBS = (
    CatalogJob(
        "JOB-SOFTWARE-ENGINEER",
        "Software Engineer",
        "Required skills: Python, Java, SQL, Git, REST APIs.\nPreferred skills: Docker, AWS, React.\nMinimum 2 years of relevant software development experience.\nBachelor's degree in Computer Science, Software Engineering, or related field.\nResponsibilities:\n- design and implement software\n- write automated tests\n- review code\n- troubleshoot production issues.",
    ),
    CatalogJob(
        "JOB-DATA-SCIENTIST",
        "Data Scientist",
        "Required skills: Python, SQL, Pandas, NumPy, Machine Learning, Statistics.\nPreferred skills: Scikit-learn, TensorFlow, Power BI.\nMinimum 2 years of relevant experience.\nMaster's or Bachelor's degree in Data Science, Statistics, Computer Science, or related field.\nResponsibilities:\n- prepare data\n- build predictive models\n- evaluate experiments\n- communicate findings.",
    ),
    CatalogJob(
        "JOB-DATA-ANALYST",
        "Data Analyst",
        "Required skills: Python, SQL, Excel, Data Analysis.\nPreferred skills: Pandas, Power BI, Tableau, Statistics.\nMinimum 1 year of relevant experience.\nBachelor's degree in Data Science, Information Technology, Business Analytics, or related field.\nResponsibilities:\n- clean data\n- create reports and dashboards\n- analyze trends\n- support business decisions.",
    ),
    CatalogJob(
        "JOB-FRONTEND-DEVELOPER",
        "Frontend Developer",
        "Required skills: JavaScript, HTML, CSS, React, Git.\nPreferred skills: TypeScript, Tailwind, Bootstrap, Material UI.\nMinimum 1 year of frontend development experience.\nBachelor's degree or diploma in Software Engineering, Computer Science, or related field.\nResponsibilities:\n- build accessible interfaces\n- integrate APIs\n- test components\n- improve user experience.",
    ),
    CatalogJob(
        "JOB-BACKEND-DEVELOPER",
        "Backend Developer",
        "Required skills: Python, Java, REST APIs, SQL, Git.\nPreferred skills: FastAPI, Flask, Spring Boot, Docker, PostgreSQL.\nMinimum 1 year of backend development experience.\nBachelor's degree or diploma in Computer Science, IT, or related field.\nResponsibilities:\n- design APIs\n- implement business logic\n- secure services\n- maintain databases.",
    ),
    CatalogJob(
        "JOB-DEVOPS-ENGINEER",
        "DevOps Engineer",
        "Required skills: Linux, Git, Docker, CI/CD, Cloud.\nPreferred skills: AWS, Kubernetes, Terraform, Python.\nMinimum 2 years of relevant DevOps or platform experience.\nBachelor's degree in IT, Computer Science, or related field.\nResponsibilities:\n- automate deployments\n- monitor systems\n- manage infrastructure\n- improve reliability.",
    ),
    CatalogJob(
        "JOB-QA-ENGINEER",
        "QA Engineer",
        "Required skills: Software Testing, Test Automation, Selenium, SQL, Git.\nPreferred skills: Pytest, Java, API Testing, CI/CD.\nMinimum 1 year of quality assurance experience.\nBachelor's degree or diploma in IT, Computer Science, or related field.\nResponsibilities:\n- design test cases\n- automate regression tests\n- report defects\n- verify releases.",
    ),
    CatalogJob(
        "JOB-IT-SUPPORT",
        "IT Support Specialist",
        "Required skills: Troubleshooting, Windows, Networking, SQL.\nPreferred skills: Linux, Cybersecurity, Cloud, Customer Support.\nMinimum 1 year of IT support experience.\nDiploma or Bachelor's degree in Information Technology or related field.\nResponsibilities:\n- resolve incidents\n- configure devices\n- document solutions\n- support users.",
    ),
)


def seed_job_catalog(session: Session) -> None:
    """Insert missing built-in jobs without overwriting recruiter data."""
    changed = False
    for item in CATALOG_JOBS:
        if session.get(JobVacancy, item.job_id) is None:
            session.add(JobVacancy(
                job_id=item.job_id,
                job_title=item.title,
                job_description=item.description,
            ))
            changed = True
    if changed:
        session.commit()
