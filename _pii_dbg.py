import spacy
try:
    nlp = spacy.load("en_core_web_sm")
    print("spacy model LOADED")
except Exception as e:
    print("spacy model NOT available:", type(e).__name__)

from backend.agents.agent1_candidate_intelligence import pii as p

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

det = p.PIIDetector()
print("nlp loaded?", det._nlp is not None)
spans = det._detect_spans(cv)
for s in sorted(spans, key=lambda x: x.start):
    print(f"  {s.start:5d}-{s.end:5d} {s.pii_type:15s} -> {cv[s.start:s.end]!r}")

print("phone regex:", [m.group(0) for m in p._PHONE_RE.finditer(cv)])