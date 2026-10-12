# Intake evidence & review timeline (Issue #41) on SQLite, reusing the #28/#30 fixtures:
# clinic "default" (staff-a, admin-a), clinic "clinic-b" (admin-b), outsider (no membership).
import json
from datetime import datetime, timezone

import pytest

from db.models import HealthRecord, ReviewEvent, WebhookDelivery
from tests.test_auth_rbac import auth, client, sessions  # noqa: F401  (pytest fixtures)

EMERGENCY_TEXT = "Sudden chest pain and shortness of breath since this morning."
BLOCKED_TEXT = "My neighbour says you have pneumonia, this is confirmed."
VAGUE_TEXT = "I just don't feel right and wanted to check in."
A = "/api/clinics/default/intakes"


def _record(id, text, *, reasons, status, safety, confidence, clinic="default", metadata=True):
    structured = {"clinical_structuring": {"symptoms": [], "clinical_summary": "s", "confidence_level": confidence}}
    if metadata:
        structured["output_metadata"] = {"generated_at": "2025-01-01T00:00:00Z", "model_version": "mock",
                                         "prompt_version": "deterministic_rule_based_baseline_v1"}
    return HealthRecord(
        id=id, trace_id=f"run-{id}", pipeline_version="v0.1.0",
        intake_json={"raw_text": text, "timestamp": "2026-01-01T09:00:00"},
        structured_output_json=structured,
        report_json={"report_sections": {"overview": "o"}}, report_text="overview: o",
        safety_audit_json=safety, clinic_id=clinic, review_status=status,
        escalation_reason=",".join(reasons) or None,
        created_at=datetime(2026, 1, 1, 9, 0, 1, tzinfo=timezone.utc),
    )


EMERGENCY_SAFETY = {
    "allowed": True, "actions": ["add_emergency_guidance"], "severity": "high", "masked_text": "x",
    "reasons": [{"type": "EMERGENCY", "detail": "Emergency or crisis signal detected", "match": "chest pain"},
                # Recorded from the generated report but absent from the input: must not be highlighted
                {"type": "EMERGENCY", "detail": "Emergency or crisis signal detected", "match": "not in input"}],
}
BLOCKED_SAFETY = {"allowed": False, "masked_text": "", "severity": "high", "actions": ["block_diagnosis"],
                  "reasons": [{"type": "MEDICAL_DIAGNOSIS", "detail": "Diagnostic certainty detected"}]}
CLEAN_SAFETY = {"allowed": True, "actions": [], "reasons": [], "severity": "low"}


@pytest.fixture
def seeded(sessions):  # noqa: F811
    with sessions() as s:
        s.add_all([
            _record("em", EMERGENCY_TEXT, reasons=["emergency_signal"], status="needs_review",
                    safety=EMERGENCY_SAFETY, confidence=1.0),
            _record("bl", BLOCKED_TEXT, reasons=["blocked_diagnosis", "low_confidence"], status="needs_review",
                    safety=BLOCKED_SAFETY, confidence=0.1),
            _record("lc", VAGUE_TEXT, reasons=["low_confidence"], status="needs_review",
                    safety=CLEAN_SAFETY, confidence=0.1),
            # Legacy record: no metadata, no timestamp, status changed before review_events existed
            HealthRecord(id="legacy", trace_id="run-legacy", pipeline_version="v0.0.1", intake_json={},
                         structured_output_json={}, report_json={"report_sections": {}}, report_text="",
                         safety_audit_json={}, clinic_id="default", review_status="reviewed"),
            _record("b-em", EMERGENCY_TEXT, reasons=["emergency_signal"], status="needs_review",
                    safety=EMERGENCY_SAFETY, confidence=1.0, clinic="clinic-b"),
        ])
        s.flush()
        s.add(WebhookDelivery(
            id="d1", idempotency_key="em:escalation", intake_id="em", event_type="intake.escalated",
            target="https://hooks.example.com", status="delivered", attempts=2, last_http_status=200,
            attempt_log=[{"attempt": 1, "outcome": "http_5xx", "http_status": 503, "at": "2026-01-01T09:00:02+00:00"},
                         {"attempt": 2, "outcome": "delivered", "http_status": 200, "at": "2026-01-01T09:00:03+00:00"}],
            created_at=datetime(2026, 1, 1, 9, 0, 2, tzinfo=timezone.utc),
            delivered_at=datetime(2026, 1, 1, 9, 0, 3, tzinfo=timezone.utc),
        ))
        s.commit()
    return sessions


@pytest.fixture
def audit_events(monkeypatch):
    events = []
    monkeypatch.setattr("api.routers.records.log_run", events.append)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda e: None)
    return events


def _timeline(client, id, who="staff-a", clinic_path=A):  # noqa: F811
    return client.get(f"{clinic_path}/{id}/timeline", headers=auth(who))


def test_requires_authentication_and_membership(client, seeded, audit_events):  # noqa: F811
    path = f"{A}/em/timeline"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer bogus"}).status_code == 401
    assert client.get(path, headers=auth("outsider")).status_code == 403
    assert audit_events == []


def test_cross_clinic_denied(client, seeded, audit_events):  # noqa: F811
    # Naming the other clinic in the path: no membership -> 403
    assert _timeline(client, "b-em", clinic_path="/api/clinics/clinic-b/intakes").status_code == 403
    # Own clinic path, other clinic's intake: indistinguishable from missing
    response = _timeline(client, "b-em")
    assert response.status_code == 404
    assert EMERGENCY_TEXT not in response.text
    assert _timeline(client, "em", who="admin-b").status_code == 403
    assert audit_events == []


def test_emergency_trigger_rule_evidence_and_highlights(client, seeded, audit_events):  # noqa: F811
    body = _timeline(client, "em").json()
    ev = body["evidence"]
    assert ev["original_input"] == EMERGENCY_TEXT
    [rule] = ev["escalation_rules"]
    assert rule["reason"] == "emergency_signal" and "Emergency" in rule["rule"]
    assert rule["evidence"]["guard_action_recorded"] is True
    assert {m["match"]: m["found_in_input"] for m in ev["recorded_matches"]} == {"chest pain": True, "not in input": False}
    assert ev["provenance"] == {"execution_mode": "mock", "model_version": "mock",
                                "prompt_version": "deterministic_rule_based_baseline_v1",
                                "pipeline_version": "v0.1.0", "run_id": "run-em"}


def test_blocked_output_and_low_confidence_triggers(client, seeded, audit_events):  # noqa: F811
    rules = {r["reason"]: r for r in _timeline(client, "bl").json()["evidence"]["escalation_rules"]}
    assert rules["blocked_diagnosis"]["evidence"]["guard_action_recorded"] is True
    assert rules["blocked_diagnosis"]["evidence"]["guard_reasons"][0]["type"] == "MEDICAL_DIAGNOSIS"
    assert rules["low_confidence"]["evidence"] == {"confidence_level": 0.1, "threshold": 0.5}

    lc = _timeline(client, "lc").json()
    assert [r["reason"] for r in lc["evidence"]["escalation_rules"]] == ["low_confidence"]
    assert lc["evidence"]["recorded_matches"] == []


def test_timeline_matches_persisted_delivery_and_transitions_in_order(client, seeded, audit_events, sessions):  # noqa: F811
    assert client.post(f"{A}/em/transition", json={"review_status": "escalated"}, headers=auth("staff-a")).status_code == 200

    body = _timeline(client, "em").json()
    kinds = [e["kind"] for e in body["events"]]
    assert kinds == ["submitted", "processed", "safety_evaluated", "escalation_decision",
                     "webhook_delivery", "staff_transition"]
    ats = [e["at"] for e in body["events"]]
    assert ats == sorted(ats)

    by_kind = {e["kind"]: e for e in body["events"]}
    with sessions() as s:
        delivery = s.get(WebhookDelivery, "d1")
        [transition] = s.query(ReviewEvent).filter_by(intake_id="em").all()
    hook = by_kind["webhook_delivery"]["details"]
    assert (hook["status"], hook["attempts"], hook["attempt_log"]) == (delivery.status, delivery.attempts, delivery.attempt_log)
    staff = by_kind["staff_transition"]["details"]
    assert staff == {"actor_id": "staff-a", "from_status": "needs_review", "to_status": "escalated"}
    assert transition.actor_id == "staff-a" and transition.clinic_id == "default"
    safety = by_kind["safety_evaluated"]["details"]
    assert safety["actions"] == ["add_emergency_guidance"] and safety["severity"] == "high"
    assert by_kind["escalation_decision"]["details"]["reasons"] == ["emergency_signal"]
    assert body["review_status"] == "escalated" and body["notes"] == []


def test_legacy_record_returns_nulls_and_notes_not_fabrications(client, seeded, audit_events):  # noqa: F811
    body = _timeline(client, "legacy").json()
    ev = body["evidence"]
    assert ev["original_input"] is None
    assert ev["provenance"]["execution_mode"] is None and ev["provenance"]["model_version"] is None
    submitted = body["events"][0]
    assert submitted["kind"] == "submitted" and submitted["at"] is None
    assert not any(e["kind"] in ("webhook_delivery", "staff_transition") for e in body["events"])
    assert len(body["notes"]) == 3


def test_audit_event_has_ids_only(client, seeded, audit_events):  # noqa: F811
    assert _timeline(client, "em").status_code == 200
    [event] = audit_events
    assert (event.action, event.resource_id, event.actor_id) == ("intake.timeline.read", "em", "staff-a")
    dumped = json.dumps(event.__dict__, default=str)
    for fragment in (EMERGENCY_TEXT, "chest pain", "shortness of breath"):
        assert fragment not in dumped
