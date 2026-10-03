import spacy
try:
    spacy.load("en_core_web_sm")
    print("spacy model LOADED")
except Exception as e:
    print("spacy model NOT available:", type(e).__name__)

from backend.agents.agent1_candidate_intelligence.pii import PIIDetector

cv = (
    "Jane Doe\n"
    "Data Analyst | Colombo, Sri Lanka\n"
    "Email: jane.doe@example.com | Phone: +94 77 123 4567\n"
    "NIC: 923456789V | Date of Birth: 12/05/1992\n"
    "Gender: Female | Marital Status: Married\n\n"
    "PROFILE\nData Analyst with 3 years experience in SQL and Excel.\n\n"
    "EDUCATION\nBSc Computer Science, University of Moratuwa\n\n"
    "SKILLS\nPython, SQL, Excel\n"
)

det = PIIDetector()
r = det.redact(cv)
print("count:", r.detected_count)
for i in r.items:
    print(f"  - {i.type:15s} | {i.detected}")
print("--- redacted ---")
print(r.redacted_text)

# safety assertions
low = r.redacted_text.lower()
for bad in ("jane", "doe", "923456789", "jane.doe", "+94 77 123", "colombo", "married"):
    assert bad not in low, f"LEAK: {bad}"
print("OK: no PII leaked into redacted text")