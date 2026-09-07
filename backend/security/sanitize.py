"""Input sanitization.

Used on every user-supplied string (job descriptions, notes, decisions) to
reduce prompt-injection and XSS/HTML-injection vectors before data reaches
the agents or the dashboard.
"""
from __future__ import annotations

import html
import re

# Strong instruction-patterns that we detect & neutralize (prompt injection guard)
_INJECTION_PATTERN = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+instructions"
    r"|disregard\s+.*instructions"
    r"|you\s+are\s+now\s+.*without\s+.*(restriction|limit)"
    r"|system\s*prompt\s*[:=]"
    r"|<\|im_start\|>|<\s*system\s*>|<\s*user\s*>)",
    re.IGNORECASE,
)

_MAX_LEN = 100_000


def sanitize_text(value: str | None, max_len: int = _MAX_LEN) -> str:
    """Escape HTML, strip control chars, cap length. Empty input -> empty string."""
    if value is None:
        return ""
    text = "".join(ch for ch in value if ch >= " " or ch in "\n\r\t")
    return html.escape(text[:max_len], quote=False)


def strip_prompt_injections(value: str | None) -> str:
    """Remove/neutralize obvious prompt-injection fragments from untrusted input."""
    text = sanitize_text(value)
    return _INJECTION_PATTERN.sub("[neutralized]", text)


def contains_suspicious_instruction(value: str | None) -> bool:
    return bool(value and _INJECTION_PATTERN.search(value))