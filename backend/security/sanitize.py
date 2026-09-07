"""Input sanitization.

Used on every user-supplied string (CV content, job descriptions, notes)
to reduce prompt-injection and control-character issues before data reaches
the agents or the dashboard.

CV content is treated as *untrusted data*: obvious instruction-like
fragments are neutralized instead of being obeyed.
"""
from __future__ import annotations

import html
import re

# Strong instruction-patterns that we detect & neutralize (prompt-injection guard).
# Deliberately conservative: it targets explicit "ignore previous instructions"
# style attacks, not creative prose.
_INJECTION_PATTERN = re.compile(
    r"(?:"
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts?|context)"
    r"|disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions"
    r"|you\s+are\s+now\s+[^.;\n]{0,60}(?:without\s+(?:any\s+)?(?:restriction|limitation|filter))"
    r"|system\s*prompt\s*[:=]"
    r"|<\|im_start\|>|<\s*system\s*>|<\s*user\s*>"
    r")",
    re.IGNORECASE,
)

_MAX_LEN = 100_000


def sanitize_text(value: str | None, max_len: int = _MAX_LEN, escape_html: bool = False) -> str:
    """Normalize free text.

    - ``None`` becomes an empty string.
    - control characters (other than newline/tab/CR) are stripped.
    - output is capped at ``max_len`` characters.
    - optionally HTML-escapes the result (for safe rendering); parsing keeps
      this off so evidence text stays readable ("C++ & Java").
    """
    if value is None:
        return ""
    text = "".join(ch for ch in value if ch >= " " or ch in "\n\r\t")
    text = _normalize_whitespace(text)
    text = text[:max_len]
    return html.escape(text, quote=False) if escape_html else text


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of blank lines and trailing spaces for stable parsing."""
    lines = [line.rstrip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line.strip() == "" and out and out[-1].strip() == "":
            continue
        out.append(line)
    return "\n".join(out).strip("\n")


def strip_prompt_injections(value: str | None) -> str:
    """Return text with obvious injection fragments neutralized."""
    text = sanitize_text(value, escape_html=False)
    return _INJECTION_PATTERN.sub("[neutralized]", text)


def contains_suspicious_instruction(value: str | None) -> bool:
    """True if the text contains obvious prompt-injection patterns."""
    return bool(value and _INJECTION_PATTERN.search(value))