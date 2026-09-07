"""Text extraction from CV documents (Agent 1).

Supports the allow-listed formats:
    PDF  -> PyMuPDF
    DOCX -> python-docx (paragraphs + tables)
    TXT/MD -> UTF-8 (with latin-1 fallback)

The extractors work on raw ``bytes`` so we never write the original
document to disk before encrypting it.
"""
from __future__ import annotations

import re
from io import BytesIO

_MULTI_BLANK = re.compile(r"\n{3,}")


class TextExtractionError(RuntimeError):
    """Raised when a document cannot be read or contains no text."""


def _clean(text: str) -> str:
    """Normalize extracted text: strip BOM, normalize newlines, collapse
    runs of blank lines and trim leading/trailing whitespace."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.lstrip("\ufeff")
    text = _MULTI_BLANK.sub("\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def extract_pdf(data: bytes) -> str:
    """Extract selectable text from a PDF loaded in memory."""
    try:
        import pymupdf  # PyMuPDF >= 1.24 public module name
    except ImportError:  # pragma: no cover - older PyMuPDF still aliases fitz
        try:
            import fitz as pymupdf  # type: ignore[no-redef]
        except ImportError as exc:
            raise TextExtractionError("PyMuPDF is not installed. Run: pip install PyMuPDF") from exc

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise TextExtractionError(f"Failed to open PDF: {exc}") from exc

    try:
        pages = [page.get_text() for page in document]
    except Exception as exc:
        raise TextExtractionError(f"Failed to read PDF pages: {exc}") from exc
    finally:
        document.close()

    return _clean("\n".join(pages))


def extract_docx(data: bytes) -> str:
    """Extract text (paragraphs + tables) from a DOCX loaded in memory."""
    try:
        from docx import Document
    except ImportError as exc:
        raise TextExtractionError("python-docx is not installed. Run: pip install python-docx") from exc

    try:
        document = Document(BytesIO(data))
    except Exception as exc:
        raise TextExtractionError(f"Failed to open DOCX: {exc}") from exc

    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return _clean("\n".join(parts))


def extract_txt(data: bytes) -> str:
    """Decode plain text (UTF-8 first, latin-1 as a fallback)."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return _clean(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise TextExtractionError("Text file could not be decoded with supported encodings.")


def extract_text(data: bytes, extension: str) -> str:
    """Dispatch to the right extractor based on the file extension.

    Returns normalized text; raises :class:`TextExtractionError` for
    unsupported formats or unreadable content.
    """
    ext = extension.lower().lstrip(".")
    if ext == "pdf":
        return extract_pdf(data)
    if ext == "docx":
        return extract_docx(data)
    if ext in ("txt", "md"):
        return extract_txt(data)
    raise TextExtractionError(f"Unsupported file type '.{ext}'.")