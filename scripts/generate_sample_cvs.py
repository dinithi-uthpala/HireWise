"""Generate fictional CV documents for HireWise demos and tests.

Run from the repository root with:
    python scripts/generate_sample_cvs.py
"""
from __future__ import annotations

from pathlib import Path

try:
    import fitz  # PyMuPDF
    from docx import Document
except ImportError as exc:  # pragma: no cover - depends on local environment
    raise SystemExit(
        "Missing document-generation dependency. Install the backend requirements "
        "with: python -m pip install -r requirements-backend.txt"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "samples" / "cvs"


SAMPLE_CVS: dict[str, list[str]] = {
    "cand_001_junior_data_analyst.pdf": [
        "Alex Morgan",
        "Email: alex.morgan@example.test | Phone: +1 555 010 1001",
        "",
        "SUMMARY",
        "Junior Data Analyst with hands-on experience preparing reports and dashboards.",
        "",
        "SKILLS",
        "Python, SQL, Excel, Power BI, Pandas",
        "",
        "EXPERIENCE",
        "Junior Data Analyst | Northstar Analytics | Jan 2023 - Present",
        "Build recurring reports, clean datasets, and support business decisions.",
        "Data Analyst Intern | Blue Oak Labs | Jun 2022 - Dec 2022",
        "Prepared SQL extracts and Excel summaries for operations teams.",
        "",
        "EDUCATION",
        "Bachelor of Science in Information Systems",
        "",
        "CERTIFICATIONS",
        "Microsoft Certified: Power BI Data Analyst",
        "",
        "PROJECTS",
        "Retail sales dashboard using Python, Pandas, SQL, and Power BI",
    ],
    "cand_002_junior_data_analyst.docx": [
        "Jamie Lee",
        "Email: jamie.lee@example.test | Phone: +1 555 010 1002",
        "",
        "SUMMARY",
        "Early-career analyst with coursework and project experience in reporting.",
        "",
        "SKILLS",
        "Excel, SQL, Python",
        "",
        "EXPERIENCE",
        "Reporting Assistant | Cedar Point Services | Jul 2024 - Present",
        "Maintain spreadsheet reports and help reconcile monthly figures.",
        "",
        "EDUCATION",
        "Bachelor of Science in Business Analytics",
        "",
        "PROJECTS",
        "Student sales analysis using Excel and SQL",
    ],
    "cand_003_manual_review.pdf": [
        "Taylor Sample",
        "",
        "PROFILE",
        "Interested in technology and data work.",
        "Experience with several tools and team projects.",
        "Available for opportunities.",
    ],
}


FAIRNESS_CV_LINES = [
    "Email: {email} | Phone: {phone}",
    "Gender: {gender}",
    "",
    "SUMMARY",
    "Data analyst with equivalent qualifications and experience for fairness testing.",
    "",
    "SKILLS",
    "Python, SQL, Excel, Power BI, Pandas",
    "",
    "EXPERIENCE",
    "Data Analyst | Equal Measure Labs | Jan 2022 - Present",
    "Create reports, clean data, and build dashboards for internal teams.",
    "",
    "EDUCATION",
    "Bachelor of Science in Information Systems",
    "",
    "CERTIFICATIONS",
    "Microsoft Certified: Power BI Data Analyst",
]


FAIRNESS_CANDIDATES = {
    "fairness_pair_a_male.docx": {
        "name": "Jordan Avery",
        "email": "jordan.avery@example.test",
        "phone": "+1 555 010 2001",
        "gender": "Male",
    },
    "fairness_pair_b_female.docx": {
        "name": "Morgan Avery",
        "email": "morgan.avery@example.test",
        "phone": "+1 555 010 2002",
        "gender": "Female",
    },
}


def _write_pdf(path: Path, lines: list[str]) -> None:
    """Write selectable text to a single-page PDF using PyMuPDF."""
    document = fitz.open()
    try:
        page = document.new_page(width=595, height=842)
        text = "\n".join(lines)
        page.insert_textbox(
            fitz.Rect(50, 45, 545, 797),
            text,
            fontsize=10,
            fontname="helv",
        )
        document.save(path)
    finally:
        document.close()


def _write_docx(path: Path, lines: list[str]) -> None:
    """Write CV lines as paragraphs so Agent 1 can extract the sections."""
    document = Document()
    for line in lines:
        paragraph = document.add_paragraph(line)
        if line.isupper() and line:
            for run in paragraph.runs:
                run.bold = True
    document.save(path)


def generate_samples() -> list[Path]:
    """Create all configured sample CV files and return their paths."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    for filename, lines in SAMPLE_CVS.items():
        path = OUTPUT_DIR / filename
        if path.suffix.lower() == ".pdf":
            _write_pdf(path, lines)
        else:
            _write_docx(path, lines)
        generated.append(path)

    for filename, values in FAIRNESS_CANDIDATES.items():
        path = OUTPUT_DIR / filename
        lines = [values["name"]] + [line.format(**values) for line in FAIRNESS_CV_LINES]
        _write_docx(path, lines)
        generated.append(path)

    return generated


def main() -> None:
    """Generate sample files and report their locations."""
    try:
        generated = generate_samples()
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"Could not generate sample CVs: {exc}") from exc

    print(f"Generated {len(generated)} sample CV files in {OUTPUT_DIR}")
    for path in generated:
        print(f"- {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
