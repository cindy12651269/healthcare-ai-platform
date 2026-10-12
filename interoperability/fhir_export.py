"""
FHIR R4 export of one stored intake (Issue #42). Export-only: builds a Bundle (type
`collection`) from persisted data; nothing is sent anywhere. Synthetic demo data only.

Resources: QuestionnaireResponse (the submission), Questionnaire (static form definition),
Task (review workflow), Organization (owning clinic), Device (AI pipeline), Provenance
(AI pipeline; plus one per recorded staff review transition). No Patient, Encounter,
Condition, Observation, medication resources or clinical coding: the data model has no
demographics and extracted symptoms are uncoded, unverified strings.

Only persisted values are used. A value that was never recorded is omitted, never filled in.
Mapping and omissions: docs/interoperability/fhir_mapping.md.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_URL, uuid5

QUESTIONNAIRE_PATH = Path(__file__).resolve().parent / "fhir" / "intake_questionnaire.json"
ID_SYSTEM = "urn:healthcare-ai-platform"
PARTICIPANT_TYPE = "http://terminology.hl7.org/CodeSystem/provenance-participant-type"

# review_status -> R4 Task.status (required binding). businessStatus keeps the exact platform value.
TASK_STATUS = {
    "submitted": "received",  # stored, not flagged for review
    "needs_review": "ready",  # waiting for staff review
    "reviewed": "completed",
    "escalated": "completed",  # review done; outcome "escalated" is in businessStatus
}


def load_questionnaire() -> Dict[str, Any]:
    with QUESTIONNAIRE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _obj(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _instant(v: Any) -> Optional[str]:
    # Naive values are UTC (intake.timestamp from datetime.utcnow(); SQLite returns naive UTC)
    if isinstance(v, str) and v:
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            return None
    if not isinstance(v, datetime):
        return None
    return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def _urn(intake_id: str, kind: str) -> str:
    # Deterministic: the same intake always exports the same fullUrls
    return f"urn:uuid:{uuid5(NAMESPACE_URL, f'{ID_SYSTEM}:{intake_id}:{kind}')}"


def _ident(kind: str, value: str) -> Dict[str, str]:
    return {"system": f"{ID_SYSTEM}:{kind}", "value": value}


def _prune(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, [], {}, "")}


def build_bundle(record: Any, clinic_name: Optional[str], review_events: List[Any]) -> Dict[str, Any]:
    intake = _obj(record.intake_json)
    metadata = _obj(_obj(record.structured_output_json).get("output_metadata"))
    questionnaire = load_questionnaire()
    # The Bundle identifies entries by urn:uuid fullUrl; the logical id stays in the repo file only
    questionnaire.pop("id", None)
    urls = {k: _urn(record.id, k) for k in ("qr", "questionnaire", "task", "org", "device", "prov-ai")}

    items = []
    if isinstance(intake.get("raw_text"), str):
        items.append({"linkId": "symptoms", "text": "Your symptoms", "answer": [{"valueString": intake["raw_text"]}]})
    if isinstance(intake.get("consent_granted"), bool):
        items.append({"linkId": "consent", "text": questionnaire["item"][1]["text"],
                      "answer": [{"valueBoolean": intake["consent_granted"]}]})
    qr = _prune({
        "resourceType": "QuestionnaireResponse",
        "identifier": _ident("intake", record.id),
        "questionnaire": questionnaire["url"],
        "status": "completed",
        "authored": _instant(intake.get("timestamp")),
        "item": items,
    })

    org = _prune({
        "resourceType": "Organization",
        "identifier": [_ident("clinic", record.clinic_id)],
        "name": clinic_name,
    })

    task = _prune({
        "resourceType": "Task",
        "identifier": [_ident("intake-review", record.id)],
        "status": TASK_STATUS.get(record.review_status, "received"),
        "businessStatus": {
            "coding": [{"system": f"{ID_SYSTEM}:review-status", "code": record.review_status}],
            "text": record.review_status,
        },
        "intent": "order",
        "description": "Staff review of a pre-visit intake",
        "focus": {"reference": urls["qr"]},
        "authoredOn": _instant(record.created_at),
        "lastModified": _instant(record.updated_at),
        "owner": {"reference": urls["org"]},
        "reasonCode": {"text": record.escalation_reason} if record.escalation_reason else None,
    })

    versions = [(label, metadata.get(key)) for label, key in (("model", "model_version"), ("prompt", "prompt_version"))]
    versions.append(("pipeline", record.pipeline_version))
    device = _prune({
        "resourceType": "Device",
        "deviceName": [{"name": "Healthcare AI Platform intake pipeline", "type": "user-friendly-name"}],
        "version": [{"type": {"text": label}, "value": value} for label, value in versions if isinstance(value, str) and value],
    })

    prov_ai = _prune({
        "resourceType": "Provenance",
        "target": [{"reference": urls["qr"]}, {"reference": urls["task"]}],
        "recorded": _instant(record.created_at),
        "activity": {"text": "AI structuring, safety check and escalation decision (run " + record.trace_id + ")"},
        "agent": [{
            "type": {"coding": [{"system": PARTICIPANT_TYPE, "code": "assembler"}]},
            "who": {"reference": urls["device"]},
        }],
    })

    entries = [
        (urls["qr"], qr),
        (urls["questionnaire"], questionnaire),
        (urls["task"], task),
        (urls["org"], org),
        (urls["device"], device),
        (urls["prov-ai"], prov_ai),
    ]
    # Human reviewer: only from persisted review history (review_events, #41)
    for ev in review_events:
        recorded = _instant(ev.created_at)
        if not recorded:
            continue
        entries.append((_urn(record.id, f"prov-review-{ev.id}"), {
            "resourceType": "Provenance",
            "target": [{"reference": urls["task"]}],
            "recorded": recorded,
            "activity": {"text": f"Staff review: {ev.from_status} -> {ev.to_status}"},
            "agent": [{
                "type": {"coding": [{"system": PARTICIPANT_TYPE, "code": "verifier"}]},
                "who": {"identifier": _ident("user", ev.actor_id)},
                "onBehalfOf": {"reference": urls["org"]},
            }],
        }))

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"tag": [{"system": f"{ID_SYSTEM}:data", "code": "synthetic-demo",
                          "display": "FHIR R4 — Synthetic Demo Data"}]},
        "entry": [{"fullUrl": url, "resource": res} for url, res in entries],
    }
