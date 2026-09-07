"""Agents package - the three collaborating intelligent agents.

Agent flow:
    Agent 1 (Candidate Intelligence) -> anonymous profile  -> Agent 2
    Agent 2 (Job Matching & Retrieval)-> score + evidence -> Agent 3
    Agent 3 (Responsible Decision)   -> recommendation    -> Human Review

Each agent communicates over the REST API using the Pydantic schemas in
`backend/schemas.py`.
"""