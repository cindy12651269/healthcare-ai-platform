"""
Intake evidence & review timeline (Issue #41). Read-only and clinic-scoped like the
#30 records API: the caller must hold a staff or admin membership of `{clinic_id}`,
and an intake owned by another clinic reads as 404.

Every value comes from persisted data (health_records, webhook_deliveries,
review_events). Nothing is re-computed or inferred beyond the documented
`execution_mode` rule; values that were never recorded are returned as null.
No model reasoning is stored or returned.
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.escalation import LOW_CONFIDENCE_THRESHOLD
from api.auth import Principal
from api.routers.records import _audit, _get_owned, staff_or_admin
from db.models import HealthRecord, ReviewEvent, WebhookDelivery
from db.session import get_db

router = APIRouter()

# Rule text for the #29 reason codes (docs/data_model.md#escalation-rules-29)
ESCALATION_RULES: Dict[str, str] = {
    "emergency_signal": "Emergency or crisis language in the intake or the generated report",
    "blocked_diagnosis": "Generated report blocked: diagnostic certainty",
    "blocked_prescription": "Generated report blocked: prescription or dosing",
    "low_confidence": f"Structuring confidence below {LOW_CONFIDENCE_THRESHOLD}",
}
_REASON_GUARD_TYPE = {
    "emergency_signal": "EMERGENCY",
    "blocked_diagnosis": "MEDICAL_DIAGNOSIS",
    "blocked_prescription": "MEDICAL_PRESCRIPTION",
}
_REASON_ACTION = {
    "emergency_signal": "add_emergency_guidance",
    "blocked_diagnosis": "block_diagnosis",
    "blocked_prescription": "block_prescription",
}
# Tie-break for events that share a timestamp
_KIND_ORDER = {"submitted": 0, "processed": 1, "safety_evaluated": 2, "escalation_decision": 3,
               "webhook_delivery": 4, "staff_transition": 5}


def _obj(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _parse(v: Any) -> Optional[datetime]:
    # Naive values are UTC: intake.timestamp comes from datetime.utcnow(), SQLite returns naive UTC
    if isinstance(v, str) and v:
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            return None
    if not isinstance(v, datetime):
        return None
    return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _iso(v: Any) -> Optional[str]:
    dt = _parse(v)
    return dt.isoformat() if dt else None


def _execution_mode(model_version: Optional[str]) -> Optional[str]:
    # The mock structuring path always records model_version "mock"; real mode records the provider model
    if not model_version:
        return None
    return "mock" if model_version == "mock" else "real"


def _reasons(record: HealthRecord) -> List[str]:
    return [r for r in (record.escalation_reason or "").split(",") if r]


def _evidence(record: HealthRecord) -> Dict[str, Any]:
    intake = _obj(record.intake_json)
    structured = _obj(record.structured_output_json)
    clinical = _obj(structured.get("clinical_structuring"))
    metadata = _obj(structured.get("output_metadata"))
    safety = _obj(record.safety_audit_json)
    raw_text = intake.get("raw_text") if isinstance(intake.get("raw_text"), str) else None
    lowered = (raw_text or "").lower()

    guard_reasons = [r for r in (safety.get("reasons") or []) if isinstance(r, dict)]
    recorded_matches = [
        {
            "type": r.get("type"),
            "detail": r.get("detail"),
            "match": r["match"],
            # Highlighted in the UI only when the recorded phrase genuinely occurs in the input
            "found_in_input": bool(raw_text) and r["match"].lower() in lowered,
        }
        for r in guard_reasons
        if isinstance(r.get("match"), str) and r["match"]
    ]

    actions = list(safety.get("actions") or [])
    confidence = clinical.get("confidence_level")
    rules = []
    for code in _reasons(record):
        guard_type = _REASON_GUARD_TYPE.get(code)
        evidence: Dict[str, Any] = {}
        if code == "low_confidence":
            evidence = {"confidence_level": confidence, "threshold": LOW_CONFIDENCE_THRESHOLD}
        elif guard_type:
            evidence = {
                "guard_action_recorded": _REASON_ACTION[code] in actions,
                "guard_reasons": [
                    {"type": r.get("type"), "detail": r.get("detail"), "match": r.get("match")}
                    for r in guard_reasons if r.get("type") == guard_type
                ],
            }
        rules.append({"reason": code, "rule": ESCALATION_RULES.get(code, "Unknown rule"), "evidence": evidence})

    return {
        "original_input": raw_text,
        "extracted": {
            key: clinical.get(key)
            for key in ("symptoms", "duration", "onset", "severity", "red_flags", "clinical_summary", "confidence_level")
        },
        "recorded_matches": recorded_matches,
        "escalation_rules": rules,
        "provenance": {
            "execution_mode": _execution_mode(metadata.get("model_version")),
            "model_version": metadata.get("model_version"),
            "prompt_version": metadata.get("prompt_version"),
            "pipeline_version": record.pipeline_version,
            "run_id": record.trace_id,
        },
    }


def _event(kind: str, at: Optional[str], at_source: str, **details) -> Dict[str, Any]:
    return {"kind": kind, "at": at, "at_source": at_source, "details": details}


def _timeline(record: HealthRecord, ev: Dict[str, Any], deliveries, transitions) -> List[Dict[str, Any]]:
    intake = _obj(record.intake_json)
    safety = _obj(record.safety_audit_json)
    stored_at = _iso(record.created_at)
    reasons = _reasons(record)

    events = [
        _event("submitted", _iso(intake.get("timestamp")), "intake.timestamp"),
        # Processing, safety and escalation happen in the pipeline before the record is stored;
        # their own times are not persisted, so they carry the record's creation time.
        _event("processed", stored_at, "record.created_at", **ev["provenance"]),
        _event(
            "safety_evaluated", stored_at, "record.created_at",
            actions=list(safety.get("actions") or []),
            reason_types=[r.get("type") for r in (safety.get("reasons") or []) if isinstance(r, dict)],
            severity=safety.get("severity"),
            recorded_matches=[m["match"] for m in ev["recorded_matches"]],
        ),
        _event("escalation_decision", stored_at, "record.created_at",
               required=bool(reasons), reasons=reasons,
               rules=[r["rule"] for r in ev["escalation_rules"]]),
    ]
    for d in deliveries:
        events.append(_event(
            "webhook_delivery", _iso(d.created_at), "webhook_deliveries.created_at",
            event_type=d.event_type, status=d.status, attempts=d.attempts,
            last_http_status=d.last_http_status, last_error=d.last_error,
            delivered_at=_iso(d.delivered_at), attempt_log=list(d.attempt_log or []),
        ))
    for t in transitions:
        events.append(_event(
            "staff_transition", _iso(t.created_at), "review_events.created_at",
            actor_id=t.actor_id, from_status=t.from_status, to_status=t.to_status,
        ))

    # Chronological; events without a recorded time keep their lifecycle position via the tie-break
    anchor = _parse(stored_at) or datetime.min.replace(tzinfo=timezone.utc)
    return sorted(events, key=lambda e: (_parse(e["at"]) or anchor, _KIND_ORDER[e["kind"]]))


@router.get("/clinics/{clinic_id}/intakes/{intake_id}/timeline")
def get_intake_timeline(
    clinic_id: str,
    intake_id: str,
    principal: Principal = Depends(staff_or_admin),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    record = _get_owned(db, clinic_id, intake_id)

    deliveries = (
        db.query(WebhookDelivery).filter(WebhookDelivery.intake_id == record.id)
        .order_by(WebhookDelivery.created_at, WebhookDelivery.id).all()
    )
    transitions = (
        db.query(ReviewEvent)
        .filter(ReviewEvent.intake_id == record.id, ReviewEvent.clinic_id == clinic_id)
        .order_by(ReviewEvent.created_at, ReviewEvent.id).all()
    )
    evidence = _evidence(record)

    notes: List[str] = []
    initial_status = "needs_review" if _reasons(record) else "submitted"
    if not transitions and record.review_status != initial_status:
        notes.append("Status changed without a recorded transition (made before transition history was stored, #41).")
    if evidence["original_input"] is None:
        notes.append("Original input text is not available in the stored record.")
    if evidence["provenance"]["model_version"] is None:
        notes.append("Model and prompt version were not recorded for this intake.")

    # Ids only: no intake text, matches or structured content in the audit event
    _audit(principal, "intake.timeline.read", clinic_id, started, resource_id=record.id)
    return {
        "intake_id": record.id,
        "clinic_id": record.clinic_id,
        "review_status": record.review_status,
        "evidence": evidence,
        "events": _timeline(record, evidence, deliveries, transitions),
        "notes": notes,
    }
