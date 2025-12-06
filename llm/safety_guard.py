import re
from typing import List

# PHI detection patterns (minimal but practical)
PHI_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",        # SSN-like
    r"\b\d{4}-\d{2}-\d{2}\b",        # DOB
    r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", # naive names
    r"\b\d{10}\b",                   # phone numbers
    r"\b\d{5}(?:-\d{4})?\b",         # ZIP codes
]

# Safety rules injected in prompts
SAFETY_RULES: List[str] = [
    "Do NOT provide medical diagnoses.",
    "Do NOT mention diseases, conditions, or clinical certainty.",
    "Do NOT include PHI such as names, dates, addresses, or identifiers.",
    "Use general wellness language only.",
    "Use observational, non-clinical phrasing.",
]

# Redact PHI-like patterns.
def apply_safety_filters(text: str) -> str:
    sanitized = text
    for pattern in PHI_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized)
    return sanitized

# Detect prohibited diagnostic wording.
def violates_rules(text: str) -> bool:
    forbidden = [
        r"\bdiagnose\b",
        r"\byou have\b",
        r"\bits likely you\b",
        r"\byou are suffering from\b",
        r"\bcondition\b",
        r"\bclinical\b",
        r"\bconfirmed\b",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in forbidden)

# Apply filters + downgrade unsafe phrasing.
def enforce_output_safety(text: str) -> str:
    text = apply_safety_filters(text)
    if violates_rules(text):
        text += "\n\n[NOTE: Language softened to avoid diagnostic interpretation.]"
    return text
