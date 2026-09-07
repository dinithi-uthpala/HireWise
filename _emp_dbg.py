import re
from backend.agents.agent1_candidate_intelligence.profile_extraction import (
    _DATE_RANGE_RE, _DATE_TOKEN_RE, _MONTH_WORDS,
)

print("MONTH_WORDS:", repr(_MONTH_WORDS))
print()
print("RANGE pattern:", _DATE_RANGE_RE.pattern)
print()
mm = _DATE_TOKEN_RE.search("Jan 2022")
print("TOKEN on 'Jan 2022':", repr(mm.group(0)) if mm else None)

probe = re.compile(r"(?i)(?:" + _MONTH_WORDS + r"[\s./-])(?:19|20)\d{2}")
m = probe.search("Data Analyst, ABC Analytics | Jan 2022 - Present")
print("probe (month required):", m.group(0) if m else None)

m2 = re.search(r"(?i)jan[\s./-](?:19|20)\d{2}", "Data Analyst, ABC Analytics | Jan 2022 - Present")
print("direct jan probe:", m2.group(0) if m2 else None)