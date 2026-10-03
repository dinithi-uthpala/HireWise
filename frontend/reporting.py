"""Small report helpers used by the Streamlit dashboard."""
from __future__ import annotations

import io
from html import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def candidate_pdf(candidate_id: str, detail: dict) -> bytes:
    """Build a compact PDF explanation without including raw CV identity data."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.6 * inch,
                                 leftMargin=0.6 * inch, topMargin=0.6 * inch,
                                 bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    summary = detail.get("summary", {})
    match = detail.get("match", {})
    review = detail.get("review", {})
    lines = [
        f"HireWise Candidate Report: {escape(candidate_id)}",
        f"AI recommendation: {escape(str(summary.get('recommendation', '')))}",
        f"Match score: {escape(str(match.get('match_score', 'Not available')))}",
        f"Extraction confidence: {escape(str(summary.get('extraction_confidence', '')))}",
        f"Explanation: {escape(str(review.get('explanation', '')))}",
        "Matched skills: " + escape(", ".join(match.get("matched_mandatory_skills", []) + match.get("matched_preferred_skills", []))),
        "Skill gaps: " + escape(", ".join(g.get("skill", "") for g in match.get("skill_gaps", []))),
        "Recruiter review required.",
    ]
    story = []
    for index, line in enumerate(lines):
        story.append(Paragraph(line, styles["Title"] if index == 0 else styles["BodyText"]))
        story.append(Spacer(1, 10))
    document.build(story)
    return buffer.getvalue()


def audit_pdf(candidate_id: str, events: list[dict]) -> bytes:
    """Build a simple audit history PDF."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"HireWise Audit History: {escape(candidate_id)}", styles["Title"]), Spacer(1, 12)]
    for event in events:
        text = f"{escape(str(event.get('ts', '')))} | {escape(str(event.get('actor', '')))} | {escape(str(event.get('action', '')))}"
        story.extend([Paragraph(text, styles["BodyText"]), Spacer(1, 8)])
    document.build(story)
    return buffer.getvalue()
