"""Deterministic rule-based extraction baseline (Issue #40).

Used by the mock structuring path. It is NOT LLM output: it matches a small synthetic
lexicon against the intake text and reports only what the text states. Limitations:
fixed vocabulary, English only, simple negation window, no context or clinical reasoning.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

EXTRACTION_METHOD = "deterministic_rule_based_baseline_v1"

# Synthetic symptom lexicon: canonical label -> surface phrases (matched on word boundaries)
SYMPTOM_LEXICON: Dict[str, List[str]] = {
    "fever": ["fever", "feverish", "high temperature"],
    "cough": ["cough", "coughing"],
    "headache": ["headache", "head hurts", "head ache"],
    "dizzy": ["dizzy", "dizziness", "lightheaded", "light-headed"],
    "chest pain": ["chest pain", "chest hurts", "chest tightness"],
    "shortness of breath": ["shortness of breath", "short of breath", "trouble breathing",
                            "difficulty breathing", "can barely breathe"],
    "tired": ["tired", "fatigue", "fatigued", "exhausted"],
    "sore throat": ["sore throat", "throat hurts", "throat is sore"],
    "abdominal pain": ["abdominal pain", "stomach pain", "stomach ache", "stomachache", "belly pain"],
    "nausea": ["nausea", "nauseous"],
    "vomiting": ["vomiting", "throwing up"],
    "rash": ["rash"],
    "fainting": ["fainted", "fainting", "passed out"],
    "numbness": ["numb", "numbness"],
    "thirst": ["thirsty", "excessive thirst"],
    "runny nose": ["runny nose"],
    "diarrhea": ["diarrhea", "diarrhoea"],
}

# Red flags: label -> phrases. Descriptive only; escalation still uses the #29 rules.
RED_FLAG_LEXICON: Dict[str, List[str]] = {
    "chest pain": SYMPTOM_LEXICON["chest pain"],
    "shortness of breath": SYMPTOM_LEXICON["shortness of breath"],
    "fainting": SYMPTOM_LEXICON["fainting"],
    "blue lips": ["lips are blue", "blue lips"],
    "self-harm risk": ["suicidal", "hurt myself", "kill myself"],
    "coughing blood": ["coughing up blood", "coughing blood"],
}

SEVERITY_LEXICON: Dict[str, List[str]] = {
    "mild": ["mild", "slight", "slightly"],
    "moderate": ["moderate"],
    "severe": ["severe", "intense", "unbearable", "worst"],
}
_SEVERITY_RANK = {"mild": 1, "moderate": 2, "severe": 3}

NEGATIONS = {"no", "not", "without", "denies", "never"}
_NEGATION_WINDOW = 3  # words before a match

_NUM = r"(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|a few|several|couple of|a couple of)"
_DURATION_RE = re.compile(
    rf"\bfor (?:the )?(?:(?:past|last) )?({_NUM} (?:hours?|days?|weeks?|months?))\b"
)
_ONSET_RE = re.compile(
    r"\b((?:since|started|began) (?:yesterday|today|last night|this morning|last week|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)|this morning|last night|"
    r"yesterday|today|suddenly)\b"
)

# Confidence = 0.1 + 0.4*[>=1 symptom] + 0.15*[>=2 symptoms] + 0.2*[duration or onset] + 0.15*[severity]
# No symptom => at most 0.45, below the #29 LOW_CONFIDENCE_THRESHOLD (0.5) => escalated for review.
CONFIDENCE_BASE = 0.1
CONFIDENCE_WEIGHTS = {"symptom": 0.4, "multiple_symptoms": 0.15, "timing": 0.2, "severity": 0.15}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("’", "'"))


def _negated(text: str, start: int) -> bool:
    preceding = re.findall(r"[a-z']+", text[:start])[-_NEGATION_WINDOW:]
    return any(w in NEGATIONS for w in preceding)


def _first_match(text: str, phrases: List[str]) -> Optional[int]:
    """Position of the earliest non-negated phrase match, or None."""
    positions = []
    for phrase in phrases:
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", text):
            if not _negated(text, m.start()):
                positions.append(m.start())
                break
    return min(positions) if positions else None


def _match_lexicon(text: str, lexicon: Dict[str, List[str]]) -> List[str]:
    found = [(pos, label) for label, phrases in lexicon.items()
             if (pos := _first_match(text, phrases)) is not None]
    return [label for _, label in sorted(found)]  # order of appearance in the text


def extract(raw_text: str) -> Dict[str, Any]:
    text = _normalize(raw_text)
    symptoms = _match_lexicon(text, SYMPTOM_LEXICON)
    red_flags = _match_lexicon(text, RED_FLAG_LEXICON)

    severities = _match_lexicon(text, SEVERITY_LEXICON)
    severity = max(severities, key=_SEVERITY_RANK.get) if severities else None

    d = _DURATION_RE.search(text)
    o = _ONSET_RE.search(text)
    duration = d.group(1) if d else None
    onset = o.group(1) if o else None

    return {
        "symptoms": symptoms,
        "duration": duration,
        "onset": onset,
        "severity": severity,
        "red_flags": red_flags,
        "confidence_level": confidence_from_coverage(symptoms, duration, onset, severity),
    }


def confidence_from_coverage(symptoms: List[str], duration: Optional[str], onset: Optional[str],
                             severity: Optional[str]) -> float:
    w = CONFIDENCE_WEIGHTS
    score = CONFIDENCE_BASE
    score += w["symptom"] if symptoms else 0.0
    score += w["multiple_symptoms"] if len(symptoms) >= 2 else 0.0
    score += w["timing"] if (duration or onset) else 0.0
    score += w["severity"] if severity else 0.0
    return round(min(score, 1.0), 2)


def build_summary(fields: Dict[str, Any]) -> str:
    if not fields["symptoms"]:
        return ("Rule-based baseline (not LLM-generated): no symptoms from the baseline lexicon "
                "were found in the intake. Staff review recommended.")
    parts = [f"Reported symptoms: {', '.join(fields['symptoms'])}"]
    for key in ("severity", "duration", "onset"):
        if fields.get(key):
            parts.append(f"{key}: {fields[key]}")
    parts.append(f"red flags: {', '.join(fields['red_flags']) if fields['red_flags'] else 'none stated'}")
    return "Rule-based baseline (not LLM-generated). " + "; ".join(parts) + "."
