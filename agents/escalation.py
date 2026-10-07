from typing import Any, Dict, List, Optional

from db.models import DEFAULT_REVIEW_STATUS
from llm.safety_guard import EMERGENCY_GUIDANCE, GuardResult, append_guidance, guard_text

# Escalation rules (Issue #29): deterministic triggers that move an intake to needs_review.
# Reason codes are stored comma-separated in health_records.escalation_reason, in this order.
REASON_EMERGENCY = "emergency_signal"
REASON_BLOCKED_DIAGNOSIS = "blocked_diagnosis"
REASON_BLOCKED_PRESCRIPTION = "blocked_prescription"
REASON_LOW_CONFIDENCE = "low_confidence"

# clinical_structuring.confidence_level (0.0–1.0) strictly below this escalates
LOW_CONFIDENCE_THRESHOLD = 0.5

ESCALATED_REVIEW_STATUS = "needs_review"


def has_emergency_signal(text: str) -> bool:
    # Reuses the safety guard's existing emergency detection; no new patterns
    return "add_emergency_guidance" in guard_text(text or "").actions


def evaluate_escalation(
    *,
    intake_text: str,
    structured: Dict[str, Any],
    safety_actions: List[str],
) -> Dict[str, Any]:
    reasons: List[str] = []

    if "add_emergency_guidance" in safety_actions or has_emergency_signal(intake_text):
        reasons.append(REASON_EMERGENCY)
    if "block_diagnosis" in safety_actions:
        reasons.append(REASON_BLOCKED_DIAGNOSIS)
    if "block_prescription" in safety_actions:
        reasons.append(REASON_BLOCKED_PRESCRIPTION)

    confidence: Optional[float] = (structured.get("clinical_structuring") or {}).get("confidence_level")
    if isinstance(confidence, (int, float)) and confidence < LOW_CONFIDENCE_THRESHOLD:
        reasons.append(REASON_LOW_CONFIDENCE)

    return {
        "required": bool(reasons),
        "review_status": ESCALATED_REVIEW_STATUS if reasons else DEFAULT_REVIEW_STATUS,
        "reasons": reasons,
        "confidence_level": confidence,
        "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
    }


# Trace-safe summary of a blocked report: actions and reason types only, never the blocked text
def blocked_safety_audit(guard: GuardResult) -> Dict[str, Any]:
    return {
        "allowed": False,
        "masked_text": "",
        "actions": list(guard.actions),
        "reasons": [{"type": r.get("type"), "detail": r.get("detail")} for r in guard.reasons],
        "severity": "high",
    }


# Controlled patient acknowledgement returned instead of a blocked report (report_output.json shape).
# Emergency guidance is the guard's unchanged EMERGENCY_GUIDANCE text.
def blocked_acknowledgement(structured: Dict[str, Any], *, emergency: bool) -> Dict[str, Any]:
    trace = structured.get("trace") or {}
    metadata = structured.get("output_metadata") or {}

    overview = (
        "Thank you, your pre-visit intake has been received. "
        "A member of your care team will review it before your visit."
    )
    if emergency:
        overview = append_guidance(overview, EMERGENCY_GUIDANCE)

    return {
        "source_struct_id": str(trace.get("input_id") or "unknown"),
        "report_sections": {
            "overview": overview,
            "symptom_analysis": "An automated summary is not available for this intake.",
            "clinical_insights": "Your intake has been sent to your care team for review.",
            "risk_summary": "If your symptoms are severe or getting worse quickly, seek urgent care.",
            "recommendations": "Please bring any questions about your symptoms to your care team.",
        },
        "input_context": f"{trace.get('input_type') or 'intake'} entry",
        "safety_checks": {
            "diagnostic_check_passed": False,
            "phi_safe": True,
            "compliance_notes": "Generated report blocked by the safety guard; intake recorded for review.",
        },
        "report_metadata": {
            "generated_at": metadata.get("generated_at") or "2025-01-01T00:00:00Z",
            "model_version": "safety_acknowledgement",
            "prompt_version": "v1",
        },
    }
