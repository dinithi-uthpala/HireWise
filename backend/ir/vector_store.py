"""Persistent, offline ChromaDB retrieval for HireWise knowledge documents."""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from backend.config import CHROMA_DIR, get_settings


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]*")
_EMBEDDING_DIMENSION = 256


@dataclass(frozen=True)
class KnowledgeDocument:
    """One approved knowledge-base document ready for indexing."""

    document_id: str
    content: str
    source: str
    category: str


@dataclass(frozen=True)
class RetrievedDocument:
    """One retrieved document with source metadata and Chroma distance."""

    document_id: str
    content: str
    source: str
    category: str
    distance: float | None = None

    @property
    def relevance(self) -> float | None:
        """Convert Chroma distance into a bounded, easy-to-display value."""
        if self.distance is None:
            return None
        return round(1.0 / (1.0 + max(0.0, self.distance)), 4)


class HashingEmbeddingFunction:
    """Small deterministic local embedding function with no model download.

    ChromaDB's current embedding-function protocol requires ``name()`` in
    addition to the callable ``input -> embeddings`` interface. The stable
    name also lets Chroma identify this embedder when reopening a collection.
    """

    _NAME = "hirewise_hashing_v1"

    @staticmethod
    def name() -> str:
        """Return the stable ChromaDB embedding-function identity."""
        return HashingEmbeddingFunction._NAME

    def get_config(self) -> dict[str, int | str]:
        """Return reproducible configuration metadata for ChromaDB."""
        return {"name": self._NAME, "dimension": _EMBEDDING_DIMENSION}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "HashingEmbeddingFunction":
        """Recreate this stateless embedder from persisted configuration."""
        return HashingEmbeddingFunction()

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        """Embed indexed documents using the shared deterministic algorithm."""
        return self(input)

    def embed_query(self, input: str | list[str]) -> list[float] | list[list[float]]:
        """Embed a query with the same dimensions and token hashing as documents."""
        if isinstance(input, str):
            return self._embed(input)
        return self(input)

    def is_legacy(self) -> bool:
        """Identify this implementation as a current, non-legacy embedder."""
        return False

    def supported_spaces(self) -> list[str]:
        """Declare the distance space configured for the Chroma collection."""
        return ["cosine"]

    @staticmethod
    def _embed(text: str) -> list[float]:
        vector = [0.0] * _EMBEDDING_DIMENSION
        tokens = _TOKEN_RE.findall(text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % _EMBEDDING_DIMENSION
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude:
            vector = [value / magnitude for value in vector]
        return vector


def initialize_vector_store(
    persist_directory: Path | str | None = None,
    collection_name: str | None = None,
):
    """Open a persistent Chroma collection using the local embedder."""
    try:
        import chromadb
    except ImportError as exc:  # pragma: no cover - dependency environment
        raise RuntimeError(
            "ChromaDB is required. Install requirements-backend.txt first."
        ) from exc

    directory = Path(persist_directory) if persist_directory else CHROMA_DIR
    directory.mkdir(parents=True, exist_ok=True)
    name = collection_name or get_settings().kb_collection
    client = chromadb.PersistentClient(path=str(directory))
    # If a development collection was created before the v1 embedder was
    # introduced, delete it once and rerun the seed script. Chroma cannot
    # safely reinterpret vectors produced by a different embedding function.
    collection = client.get_or_create_collection(
        name=name,
        embedding_function=HashingEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    return client, collection


def index_documents(
    documents: Sequence[KnowledgeDocument],
    persist_directory: Path | str | None = None,
    collection_name: str | None = None,
) -> int:
    """Upsert approved documents and return the number indexed."""
    if not documents:
        return 0
    _, collection = initialize_vector_store(persist_directory, collection_name)
    collection.upsert(
        ids=[document.document_id for document in documents],
        documents=[document.content for document in documents],
        metadatas=[
            {"source": document.source, "category": document.category}
            for document in documents
        ],
    )
    return len(documents)


def retrieve_relevant_criteria(
    query: str,
    top_k: int = 3,
    persist_directory: Path | str | None = None,
    collection_name: str | None = None,
) -> list[RetrievedDocument]:
    """Retrieve the nearest approved documents for a job or role query."""
    if not query.strip() or top_k <= 0:
        return []
    _, collection = initialize_vector_store(persist_directory, collection_name)
    if collection.count() == 0:
        return []

    result: dict[str, Any] = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    retrieved: list[RetrievedDocument] = []
    for index, document_id in enumerate(ids):
        metadata = metadatas[index] or {}
        retrieved.append(
            RetrievedDocument(
                document_id=document_id,
                content=documents[index],
                source=str(metadata.get("source", "")),
                category=str(metadata.get("category", "")),
                distance=float(distances[index]) if distances else None,
            )
        )
    return retrieved
