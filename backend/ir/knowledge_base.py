"""Load and seed approved Markdown knowledge for Agent 2 retrieval."""
from __future__ import annotations

import re
from pathlib import Path

from backend.config import KB_DOCS_DIR
from backend.ir.vector_store import KnowledgeDocument, index_documents

_FRONT_MATTER = re.compile(r"\A---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z", re.DOTALL)


def load_knowledge_documents(
    docs_directory: Path | str | None = None,
) -> list[KnowledgeDocument]:
    """Load Markdown files, excluding README planning notes."""
    directory = Path(docs_directory) if docs_directory else KB_DOCS_DIR
    documents: list[KnowledgeDocument] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        metadata, body = _parse_front_matter(content)
        documents.append(
            KnowledgeDocument(
                document_id=metadata.get("id", path.stem),
                content=body,
                source=path.name,
                category=metadata.get("category", path.stem),
            )
        )
    return documents


def seed_knowledge_base(
    docs_directory: Path | str | None = None,
    persist_directory: Path | str | None = None,
    collection_name: str | None = None,
) -> int:
    """Load approved documents and upsert them into persistent ChromaDB."""
    documents = load_knowledge_documents(docs_directory)
    return index_documents(documents, persist_directory, collection_name)


def _parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    """Parse simple ``key: value`` front matter without adding PyYAML."""
    match = _FRONT_MATTER.match(content)
    if not match:
        return {}, content
    metadata: dict[str, str] = {}
    for line in match.group("meta").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() and value.strip():
            metadata[key.strip()] = value.strip()
    return metadata, match.group("body").strip()
