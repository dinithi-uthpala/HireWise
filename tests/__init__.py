"""Tests package.

Planned test files:
    test_agent1_extraction.py   nested PII removal + skill/education/experience
    test_agent2_matching.py     scoring formula, skill normalization, gaps
    test_agent3_review.py       fairness, review rules, privacy checks
    test_security.py            JWT/RBAC, file upload guards, sanitization
    test_api.py                 end-to-end REST flow (httpx / TestClient)

Run locally with:  py -m pytest tests -v
"""