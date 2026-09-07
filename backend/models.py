"""SQLModel ORM tables for HireWise.

Planned tables:
    user           HR users + roles (Recruiter, HR Admin, Viewer)
    jobvacancy     job descriptions posted by recruiters
    candidate      uploaded CVs (encrypted), extracted profile, PII report
    matchresult    Agent 2 component scores + evidence
    aireview       Agent 3 recommendation + risk flags
    humandecision  final recruiter decision (shortlist / hold / not selected)
    auditlog       immutable audit trail
    agentactivity  live agent-communication monitor feed
"""

# TODO(Team): define the SQLModel table classes listed above.