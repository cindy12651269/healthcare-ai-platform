"""
Read-only system card (Issue #43): pipeline stages, current execution mode, the existing
safety and escalation rules, and the committed #32 / #40 evaluation snapshot
(evaluation/system_card_results.json, kept in sync by tests/test_system_card.py).
Public and non-sensitive: no intake data, no configuration secrets.
"""
from typing import Any, Dict

from fastapi import APIRouter

from agents.escalation import LOW_CONFIDENCE_THRESHOLD
from api.config import get_settings
from api.routers.timeline import ESCALATION_RULES
from evaluation.system_card import load_results

router = APIRouter()

NOT_A_MEDICAL_DEVICE = (
    "Not a medical device. This is a portfolio demonstration on synthetic data. It does not diagnose, "
    "prescribe or provide medical advice, is not clinically validated, and makes no regulatory or "
    "compliance claim (including HIPAA)."
)

PIPELINE_STAGES = [
    {"stage": "Intake", "description": "Validates the submission and consent, detects PHI patterns, assigns ids."},
    {"stage": "Structuring", "description": "Extracts symptoms, duration, onset, severity and red flags. Mock mode: deterministic rule-based baseline (#40), not LLM output."},
    {"stage": "Report + safety guard", "description": "Generates the patient report; the rule-based guard blocks diagnosis/prescription content, masks PHI patterns and adds emergency guidance."},
    {"stage": "Escalation", "description": "Deterministic #29 rules set needs_review with reason codes."},
    {"stage": "Persistence + notification", "description": "Stores the record for the clinic; escalated intakes trigger a signed, PHI-free webhook (#33)."},
    {"stage": "Staff review", "description": "Clinic staff review the queue, evidence and timeline (#41) and can export FHIR R4 (#42)."},
]

# The guard's existing behaviour (llm/safety_guard.py); descriptive, not new rules
SAFETY_RULES = [
    {"action": "block_diagnosis", "description": "Blocks a generated report containing diagnostic certainty."},
    {"action": "block_prescription", "description": "Blocks a generated report containing prescription or dosing content."},
    {"action": "add_emergency_guidance", "description": "Adds emergency guidance when emergency or crisis language is detected."},
    {"action": "mask_phi", "description": "Masks PHI patterns (email, phone, IDs, dates, SSN, contextual names) in report text."},
]

KNOWN_LIMITATIONS = [
    "Safety guard and escalation are keyword/regex rules; paraphrases can be missed (known gaps in #32).",
    "Mock-mode extraction is a small fixed lexicon; anything outside it is missed and lowers confidence.",
    "Evaluation sets are tiny and synthetic; results are not clinical accuracy.",
    "Retrieval (RAG) is not wired into the API; mock embeddings carry no meaning.",
    "Raw intake text is stored unmasked and returned to authorized staff (timeline, FHIR export).",
    "No HIPAA compliance, encryption at the application level, or rate limiting.",
]


@router.get("/system-card")
def system_card() -> Dict[str, Any]:
    return {
        "not_a_medical_device": NOT_A_MEDICAL_DEVICE,
        "execution_mode": get_settings().llm_mode,
        "pipeline_stages": PIPELINE_STAGES,
        "safety_rules": SAFETY_RULES,
        "escalation_rules": [{"reason": code, "rule": rule} for code, rule in ESCALATION_RULES.items()],
        "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
        "evaluation": load_results(),
        "known_limitations": KNOWN_LIMITATIONS,
    }
