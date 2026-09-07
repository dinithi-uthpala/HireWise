"""HireWise Backend package.

Layout:
    main.py      FastAPI entry point
    config.py    pydantic-settings configuration
    database.py  SQLModel engine + session
    models.py    ORM tables
    schemas.py   Pydantic agent-communication contracts
    agents/      the three collaborating agents
    api/         REST API route modules
    ir/          Information Retrieval (ChromaDB + skill taxonomy)
    security/    JWT / RBAC / PII / encryption / sanitization
"""