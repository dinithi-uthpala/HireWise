import io

from backend.agents.agent1_candidate_intelligence import process_cv
from backend.security.files import load_encrypted

CV = """Kavindu Perera
Junior Data Analyst
Email: kavindu.perera@mail.com | Phone: +94 71 234 5678
NIC: 923456789V

PROFILE
Junior Data Analyst with 2 years of experience in SQL, Python and Excel.

SKILLS
Python, SQL, Excel, Power BI, Statistics, Communication, Teamwork

EXPERIENCE
Data Analyst, ABC Analytics | Jan 2022 - Present
- Built dashboards and cleaned datasets using Python and Excel
Data Analyst Intern, XYZ Corp | Jan 2021 - Dec 2021
- Assisted with SQL queries and reporting

EDUCATION
BSc (Hons) in Computer Science, University of Moratuwa (2019 - 2021)

CERTIFICATIONS
Google Data Analytics Certificate
Certified in SQL for Data Science

PROJECTS
Sales Dashboard (Power BI)
Customer Churn Analysis (Python)
"""

result = process_cv("cv.txt", CV.encode("utf-8"))
print("candidate_id:", result.candidate_id)
print("status:", result.parse_status, "| confidence:", result.extraction_confidence)
print("method:", result.extraction_method)
print("pii items:", [(i.type, i.detected) for i in result.pii.items])
print("stored:", result.stored_cv_path)
p = result.profile
print("skills:", p.technical_skills)
print("soft:", p.soft_skills)
print("titles:", p.job_titles)
print("employers:", p.employers)
print("education:", [(e.qualification_level, e.subject) for e in p.education])
print("certs:", p.certifications)
print("projects:", p.projects)
print("years:", p.total_experience_years)
print("warnings:", result.warnings)

# encryption round-trip on the stored original
original = load_encrypted(result.stored_cv_path).decode("utf-8")
assert original == CV, "stored CV does not round-trip!"
print("OK: encrypted original round-trips")

# privacy assertions on the profile payload
blob = p.model_dump_json().lower()
for bad in ("kavindu", "perera", "923456789", "kavindu.perera", "+94 71 234"):
    assert bad not in blob, f"PII LEAK into profile: {bad}"
print("OK: anonymous profile contains no PII")