"""Pydantic schemas = the typed JSON contract between agents.

These schemas define the agent-communication protocol over REST + JSON
and are validated on every hop (ExtractionResult, MatchResultData,
ReviewOutput, FairnessTestResult, ...).
"""

# TODO(Team): add Pydantic models for Agent 1/2/3 payloads and API bodies.