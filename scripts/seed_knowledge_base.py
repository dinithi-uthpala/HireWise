"""Index approved HireWise knowledge-base documents into ChromaDB."""
from __future__ import annotations

import sys
from pathlib import Path

# Running a script by path places ``scripts/`` first on sys.path. Ensure the
# import below resolves this repository's backend package, not another install.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ir.knowledge_base import seed_knowledge_base


def main() -> None:
    """Seed the configured persistent knowledge base."""
    count = seed_knowledge_base()
    print(f"Indexed {count} knowledge-base document(s) into ChromaDB.")


if __name__ == "__main__":
    main()
