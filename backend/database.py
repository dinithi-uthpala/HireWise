"""Database engine + session helpers.

Relational store for structured data:
  - default: SQLite  (data/hirewise.db, zero configuration)
  - production: PostgreSQL via the DATABASE_URL env var

The vector store used by the Information Retrieval module lives in
`backend/ir/` (ChromaDB) and is intentionally separate.
"""

# TODO(Team): add SQLModel engine (create_engine), create_db_and_tables()
#             and a get_session() FastAPI dependency.