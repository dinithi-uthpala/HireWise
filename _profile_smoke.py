from backend.agents.agent1_candidate_intelligence.pii import PIIDetector
from backend.agents.agent1_candidate_intelligence.profile_extraction import (
    extract_profile, split_sections,
)

cv = """Kavindu Perera
Data Analyst | Colombo
Email: kavindu.perera@mail.com | Phone: +94 71 234 5678

PROFILE
Junior Data Analyst with 2 years of experience in SQL, Python and Excel.

SKILLS
Python, SQL, Excel, Power BI, Statistics, Communication, Teamwork

EXPERIENCE
Data Analyst, ABC Analytics | Jan 2022 - Present
- Built dashboards and cleaned datasets using Python and Excel
Data Analyst Intern, XYZ Corp | Jan 2021 - Dec 2021
- Assisted with SQL queries and reporting. Used Power BI for visualization

EDUCATION
BSc (Hons) in Computer Science, University of Moratuwa (2019 - 2021)

CERTIFICATIONS
Google Data Analytics Certificate
Certified in SQL for Data Science

PROJECTS
Sales Dashboard (Power BI)
Customer Churn Analysis (Python)
"""

r = PIIDetector().redact(cv)
print("== PII ==", r.detected_count, "items")
print(r.redacted_text)
print()
print("== SECTIONS ==", sorted(split_sections(r.redacted_text).keys()))
print()
profile = extract_profile("CAND-001", r.redacted_text)
print("== PROFILE ==")
print("skills:", profile.technical_skills)
print("soft:", profile.soft_skills)
print("titles:", profile.job_titles)
print("employers:", profile.employers)
print("education:", [(e.qualification_level, e.subject) for e in profile.education])
print("certs:", profile.certifications)
print("projects:", profile.projects)
print("experience_years:", profile.total_experience_years)
for entry in profile.experience_entries:
    print(f"  exp: {entry.role} @ {entry.employer} {entry.start}->{entry.end} = {entry.months:.0f} mo")