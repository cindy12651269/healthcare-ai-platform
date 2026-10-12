# FHIR R4 export (Issue #42) on SQLite, reusing the #28/#30 fixtures: clinic "default"
# (staff-a, admin-a), clinic "clinic-b" (admin-b), outsider. Synthetic data only.
import json
from datetime import datetime, timezone

import pytest

from db.models import HealthRecord
from interoperability.fhir_export import build_bundle, load_questionnaire
from interoperability.fhir_validation import (
    SCHEMA_SHA256, SCHEMA_ZIP, check_references, load_schema, validate_bundle, validate_resource,
)
from tests.test_auth_rbac import auth, client, sessions  # noqa: F401  (pytest fixtures)

TEXT = "Synthetic: sore throat and mild fever for two days."
A = "/api/clinics/default/intakes"


def _record(id, clinic="default", status="needs_review", reason="low_confidence", metadata=True):
    structured = {"clinical_structuring": {"symptoms": ["sore throat"], "clinical_summary": "s", "confidence_level": 0.4}}
    if metadata:
        structured["output_metadata"] = {"generated_at": "2025-01-01T00:00:00Z", "model_version": "mock",
                                         "prompt_version": "deterministic_rule_based_baseline_v1"}
    return HealthRecord(
        id=id, trace_id=f"run-{id}", pipeline_version="v0.1.0",
        intake_json={"raw_text": TEXT, "timestamp": "2026-01-01T09:00:00", "consent_granted": True},
        structured_output_json=structured,
        report_json={"report_sections": {"overview": "o"}}, report_text="overview: o",
        safety_audit_json={"allowed": True, "actions": [], "reasons": [], "severity": "low"},
        clinic_id=clinic, review_status=status, escalation_reason=reason,
        created_at=datetime(2026, 1, 1, 9, 0, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, 9, 0, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def seeded(sessions):  # noqa: F811
    with sessions() as s:
        s.add_all([_record("a1"), _record("b1", clinic="clinic-b")])
        s.commit()
    return sessions


@pytest.fixture
def audit_events(monkeypatch):
    events = []
    monkeypatch.setattr("api.routers.records.log_run", events.append)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda e: None)
    return events


def _by_type(bundle):
    out = {}
    for e in bundle["entry"]:
        out.setdefault(e["resource"]["resourceType"], []).append(e)
    return out


# Validator

def test_validator_is_pinned_official_r4_schema():
    import hashlib
    assert hashlib.sha256(SCHEMA_ZIP.read_bytes()).hexdigest() == SCHEMA_SHA256
    assert "Task" in load_schema()["discriminator"]["mapping"]


def test_validator_rejects_invalid_resources():
    assert validate_resource({"resourceType": "Task", "status": "needs_review", "intent": "order"})
    bad = {"resourceType": "Bundle", "type": "collection",
           "entry": [{"fullUrl": "urn:uuid:1", "resource": {"resourceType": "Task", "status": "ready", "intent": "order",
                                                            "focus": {"reference": "urn:uuid:missing"}}}]}
    assert check_references(bad) == ["unresolved reference urn:uuid:missing"]
    assert any("intent: required" in e for e in validate_bundle(
        {"resourceType": "Bundle", "type": "collection", "entry": [{"fullUrl": "urn:uuid:1",
                                                                   "resource": {"resourceType": "Task", "status": "ready"}}]}))


def test_static_questionnaire_is_valid_r4():
    assert validate_resource(load_questionnaire()) == []


# The Questionnaire must record exactly what the patient saw on the intake form (no invented wording)
def test_questionnaire_item_texts_match_intake_form_verbatim():
    import re
    from pathlib import Path
    form = Path(__file__).resolve().parent.parent / "app" / "components" / "InputForm.tsx"
    form_text = re.sub(r"\s+", " ", form.read_text(encoding="utf-8"))
    items = {i["linkId"]: i["text"] for i in load_questionnaire()["item"]}
    assert items["symptoms"] == "Your symptoms"
    assert items["consent"] == "I consent to this information being processed to prepare a summary for my care team."
    for text in items.values():
        assert f">{text}<" in form_text.replace("> ", ">").replace(" <", "<"), text


# Deterministic synthetic fixture: interoperability/fhir/examples/synthetic_reviewed_intake_bundle.json
FIXTURE = SCHEMA_ZIP.parent / "examples" / "synthetic_reviewed_intake_bundle.json"


def _fixture_bundle():
    from types import SimpleNamespace
    record = _record("synthetic-0001", status="reviewed")
    record.updated_at = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    event = SimpleNamespace(id="ev-1", actor_id="staff-a", from_status="needs_review", to_status="reviewed",
                            created_at=datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc))
    return build_bundle(record, "Default Clinic", [event])


def test_synthetic_fixture_is_valid_and_matches_exporter():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert validate_bundle(fixture) == []
    assert _fixture_bundle() == fixture


# Export endpoint

def test_requires_authentication_and_membership(client, seeded, audit_events):  # noqa: F811
    path = f"{A}/a1/fhir"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer bogus"}).status_code == 401
    assert client.get(path, headers=auth("outsider")).status_code == 403
    assert audit_events == []


def test_cross_clinic_export_denied(client, seeded, audit_events):  # noqa: F811
    assert client.get("/api/clinics/clinic-b/intakes/b1/fhir", headers=auth("staff-a")).status_code == 403
    response = client.get(f"{A}/b1/fhir", headers=auth("staff-a"))
    assert response.status_code == 404 and TEXT not in response.text
    assert client.get(f"{A}/a1/fhir", headers=auth("admin-b")).status_code == 403
    assert audit_events == []


def test_export_is_valid_r4_and_reflects_current_task_status(client, seeded, audit_events):  # noqa: F811
    response = client.get(f"{A}/a1/fhir", headers=auth("staff-a"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/fhir+json")
    bundle = response.json()
    assert validate_bundle(bundle) == []
    assert bundle["type"] == "collection"
    assert bundle["meta"]["tag"][0]["display"] == "FHIR R4 — Synthetic Demo Data"

    types = _by_type(bundle)
    assert set(types) == {"QuestionnaireResponse", "Questionnaire", "Task", "Organization", "Device", "Provenance"}
    assert not {"Patient", "Encounter", "Condition", "Observation"} & set(types)

    qr = types["QuestionnaireResponse"][0]
    answers = {i["linkId"]: i["answer"][0] for i in qr["resource"]["item"]}
    consent_text = next(i["text"] for i in qr["resource"]["item"] if i["linkId"] == "consent")
    assert consent_text == "I consent to this information being processed to prepare a summary for my care team."
    assert answers == {"symptoms": {"valueString": TEXT}, "consent": {"valueBoolean": True}}
    assert qr["resource"]["authored"] == "2026-01-01T09:00:00+00:00"
    assert qr["resource"]["questionnaire"] == types["Questionnaire"][0]["resource"]["url"]

    task = types["Task"][0]["resource"]
    assert (task["status"], task["businessStatus"]["text"]) == ("ready", "needs_review")
    assert task["reasonCode"]["text"] == "low_confidence"
    assert task["focus"]["reference"] == qr["fullUrl"]
    assert task["owner"]["reference"] == types["Organization"][0]["fullUrl"]
    assert types["Organization"][0]["resource"]["identifier"][0]["value"] == "default"

    [prov] = types["Provenance"]  # AI only: no review recorded yet
    assert prov["resource"]["agent"][0]["who"]["reference"] == types["Device"][0]["fullUrl"]
    versions = {v["type"]["text"]: v["value"] for v in types["Device"][0]["resource"]["version"]}
    assert versions == {"model": "mock", "prompt": "deterministic_rule_based_baseline_v1", "pipeline": "v0.1.0"}

    # Deterministic
    assert client.get(f"{A}/a1/fhir", headers=auth("staff-a")).json() == bundle


def test_reviewer_provenance_after_transition(client, seeded, audit_events):  # noqa: F811
    assert client.post(f"{A}/a1/transition", json={"review_status": "escalated"}, headers=auth("admin-a")).status_code == 200
    bundle = client.get(f"{A}/a1/fhir", headers=auth("staff-a")).json()
    assert validate_bundle(bundle) == []
    types = _by_type(bundle)

    task = types["Task"][0]["resource"]
    assert (task["status"], task["businessStatus"]["text"]) == ("completed", "escalated")
    review = [p["resource"] for p in types["Provenance"]
              if p["resource"]["agent"][0]["type"]["coding"][0]["code"] == "verifier"]
    assert len(review) == 1
    assert review[0]["agent"][0]["who"]["identifier"]["value"] == "admin-a"
    assert review[0]["target"] == [{"reference": types["Task"][0]["fullUrl"]}]


def test_missing_metadata_is_omitted_not_invented(seeded):
    record = _record("legacy", metadata=False, status="reviewed", reason=None)
    record.intake_json = {}
    bundle = build_bundle(record, None, [])
    assert validate_bundle(bundle) == []
    types = _by_type(bundle)
    assert "item" not in types["QuestionnaireResponse"][0]["resource"]
    assert "authored" not in types["QuestionnaireResponse"][0]["resource"]
    assert "reasonCode" not in types["Task"][0]["resource"]
    assert "name" not in types["Organization"][0]["resource"]
    # Reviewed without a recorded transition: no reviewer is invented
    assert len(types["Provenance"]) == 1
    assert [v["type"]["text"] for v in types["Device"][0]["resource"]["version"]] == ["pipeline"]


def test_export_audit_event_has_actor_and_ids_only(client, seeded, audit_events):  # noqa: F811
    assert client.get(f"{A}/a1/fhir", headers=auth("staff-a")).status_code == 200
    [event] = audit_events
    assert (event.action, event.actor_id, event.resource_id) == ("intake.fhir_export", "staff-a", "a1")
    dumped = json.dumps(event.__dict__, default=str)
    for fragment in (TEXT, "QuestionnaireResponse", "sore throat"):
        assert fragment not in dumped
