from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

# Data Structures
@dataclass(frozen=True)
class GuardReason:
    type: str
    detail: str
    match: Optional[str] = None


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    masked_text: str
    actions: List[str]
    reasons: List[Dict[str, Any]]
    severity: str  # "low" | "medium" | "high"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "masked_text": self.masked_text,
            "actions": list(self.actions),
            "reasons": list(self.reasons),
            "severity": self.severity,
        }

# Safety Rules (Prompt-Injectable)
SAFETY_RULES: List[str] = [
    "Do NOT provide medical diagnoses or clinical certainty.",
    "Do NOT prescribe medications, dosing, or tell users to start/stop drugs.",
    "Do NOT include PHI (names, dates, addresses, identifiers). Mask any PHI.",
    "Use general wellness / educational language only.",
    "If emergency symptoms are present, advise seeking urgent care.",
]

# PHI Masking (Deterministic)
PHI_REPLACEMENTS: Dict[str, str] = {
    "PHI_SSN": "[PHI_SSN]",
    "PHI_EMAIL": "[PHI_EMAIL]",
    "PHI_PHONE": "[PHI_PHONE]",
    "PHI_DATE": "[PHI_DATE]",
    "PHI_ID": "[PHI_ID]",
    "PHI_ZIP": "[PHI_ZIP]",
    "PHI_NAME": "[PHI_NAME]",
}

PHI_PATTERNS: List[Tuple[str, str]] = [
    ("PHI_SSN", r"\b\d{3}-\d{2}-\d{4}\b"),
    ("PHI_EMAIL", r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    ("PHI_PHONE", r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b"),
    ("PHI_DATE", r"\b\d{4}-\d{2}-\d{2}\b"),
    ("PHI_DATE", r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ("PHI_ZIP", r"\b\d{5}(?:-\d{4})?\b"),
    ("PHI_ID", r"\b(?:MRN|ID|Patient\s*ID|Record\s*ID)\s*[:#]?\s*[A-Z0-9-]{4,}\b"),
    # Weak / contextual name detection (Phase 1–2 safe)
    ("PHI_NAME", r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b"),
]

NAME_CONTEXT_HINTS = [
    "call me",
    "contact",
    "reached at",
    "has",
    "patient",
]


def _mask_phi(text: str) -> Tuple[str, List[GuardReason]]:
    masked = text
    reasons: List[GuardReason] = []

    # Strong PHI first (email, phone, id, date, ssn, zip)
    for phi_type, pattern in PHI_PATTERNS:
        if phi_type == "PHI_NAME":
            continue

        for m in re.finditer(pattern, masked, flags=re.IGNORECASE):
            reasons.append(
                GuardReason(
                    type="PHI",
                    detail=f"{phi_type} detected",
                    match=m.group(0),
                )
            )

        masked = re.sub(
            pattern,
            PHI_REPLACEMENTS.get(phi_type, "[PHI_REDACTED]"),
            masked,
            flags=re.IGNORECASE,
        )

    # Weak PHI (names) — contextual & last
    for phi_type, pattern in PHI_PATTERNS:
        if phi_type != "PHI_NAME":
            continue

        lower = masked.lower()
        if not any(hint in lower for hint in NAME_CONTEXT_HINTS):
            continue

        for m in re.finditer(pattern, masked):
            reasons.append(
                GuardReason(
                    type="PHI",
                    detail="PHI_NAME detected",
                    match=m.group(0),
                )
            )

        masked = re.sub(pattern, PHI_REPLACEMENTS["PHI_NAME"], masked)

    return masked, reasons

# Rule Patterns
DIAGNOSIS_PATTERNS: List[str] = [
    r"\bdiagnos(?:e|is)\b",
    r"\byou have\b",
    r"\bits likely you\b",
    r"\byou are suffering from\b",
    r"\bconfirmed\b",
    r"\bclinically\b",
]

PRESCRIPTION_PATTERNS: List[str] = [
    r"\bprescrib(?:e|ed|ing)\b",
    r"\btake\s+\d+\s*(?:mg|g|mcg|ml)\b",
    r"\bstart\s+(?:taking|using)\b.*\b(medication|drug|antibiotic)\b",
    r"\bstop\s+(?:taking|using)\b.*\b(medication|drug|antidepressant|insulin)\b",
]

EMERGENCY_PATTERNS: List[str] = [
    r"\bchest pain\b",
    r"\btrouble breathing\b",
    r"\bshortness of breath\b",
    r"\bfaint(?:ed|ing)?\b",
    r"\bsevere bleeding\b",
    r"\bstroke\b",
    r"\bsuicid(?:al|e)\b",
    r"\bkill myself\b",
    r"\bself harm\b",
]

EMERGENCY_GUIDANCE = (
    "If you are experiencing severe or rapidly worsening symptoms, or you might be in danger, "
    "please seek urgent medical care immediately. If you are in the U.S., call 911. "
    "If you are outside the U.S., contact your local emergency number or a trusted local crisis service."
)


def _match_any(patterns: List[str], text: str) -> Optional[str]:
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return p
    return None

# Public API
def guard_text(text: str) -> GuardResult:
    original = text or ""
    actions: List[str] = []
    reasons: List[GuardReason] = []
    allowed = True
    severity = "low"

    # Diagnosis block
    if _match_any(DIAGNOSIS_PATTERNS, original):
        allowed = False
        actions.append("block_diagnosis")
        reasons.append(
            GuardReason(
                type="MEDICAL_DIAGNOSIS",
                detail="Diagnostic certainty detected",
            )
        )
        severity = "high"

    # Prescription block
    if _match_any(PRESCRIPTION_PATTERNS, original):
        allowed = False
        actions.append("block_prescription")
        reasons.append(
            GuardReason(
                type="MEDICAL_PRESCRIPTION",
                detail="Prescription or dosing detected",
            )
        )
        severity = "high"

    # Emergency detection
    emergency_hit = _match_any(EMERGENCY_PATTERNS, original)
    if emergency_hit:
        actions.append("add_emergency_guidance")
        reasons.append(
            GuardReason(
                type="EMERGENCY",
                detail="Emergency or crisis signal detected",
                match=emergency_hit,
            )
        )
        severity = "high"

    # PHI masking (output-only)
    masked, phi_reasons = _mask_phi(original)
    if phi_reasons:
        actions.append("mask_phi")
        reasons.extend(phi_reasons)
        severity = max_severity(severity, "medium")

    # Append emergency guidance after masking
    if emergency_hit:
        masked = append_guidance(masked, EMERGENCY_GUIDANCE)

    return GuardResult(
        allowed=allowed,
        masked_text=masked,
        actions=actions,
        reasons=[asdict(r) for r in reasons],
        severity=severity,
    )


def append_guidance(text: str, guidance: str) -> str:
    text = (text or "").rstrip()
    if guidance in text:
        return text
    return f"{text}\n\n{guidance}"


def max_severity(a: str, b: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return a if order[a] >= order[b] else b
