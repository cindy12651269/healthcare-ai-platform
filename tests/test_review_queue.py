# Records & review-queue API (Issue #30) on SQLite, reusing the #28 auth fixtures:
# clinic "default" (staff-a: clinic_staff, admin-a: clinic_admin), clinic "clinic-b" (admin-b), outsider (no membership).
import json

import pytest

from db.models import HealthRecord
from tests.test_auth_rbac import auth, client, sessions  # noqa: F401  (pytest fixtures)

RAW_TEXT = "Distinctive raw intake text: sore throat since Tuesday"

A = "/api/clinics/default/intakes"
B = "/api/clinics/clinic-b/intakes"


def _record(id, clinic_id, review_status, escalation_reason=None):
    return HealthRecord(
        id=id,
        trace_id=f"trace-{id}",
        pipeline_version="test",
        intake_json={"raw_text": RAW_TEXT},
        structured_output_json={"clinical_structuring": {"confidence_level": 0.9}},
        report_json={"report_sections": {"overview": "Pre-visit intake received."}},
        report_text="overview: Pre-visit intake received.",
        safety_audit_json={"allowed": True, "actions": [], "reasons": [], "severity": "low"},
        clinic_id=clinic_id,
        review_status=review_status,
        escalation_reason=escalation_reason,
    )


@pytest.fixture
def seeded(sessions):  # noqa: F811
    with sessions() as s:
        s.add_all([
            _record("a-flagged", "default", "needs_review", "emergency_signal"),
            _record("a-flagged-2", "default", "needs_review", "low_confidence"),
            _record("a-normal", "default", "submitted"),
            _record("a-reviewed", "default", "reviewed"),
            _record("b-flagged", "clinic-b", "needs_review", "blocked_diagnosis"),
        ])
        s.commit()
    return sessions


@pytest.fixture
def audit_events(monkeypatch):
    events = []
    monkeypatch.setattr("api.routers.records.log_run", events.append)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda e: None)
    return events


def _status(sessions, id):  # noqa: F811
    with sessions() as s:
        return s.get(HealthRecord, id).review_status


# Authentication and role

@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", A, None),
        ("get", f"{A}/a-flagged", None),
        ("post", f"{A}/a-flagged/transition", {"review_status": "reviewed"}),
    ],
)
def test_every_endpoint_requires_authentication_and_membership(client, seeded, audit_events, method, path, body):  # noqa: F811
    kwargs = {"json": body} if body else {}

    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert getattr(client, method)(path, headers={"Authorization": "Bearer bogus"}, **kwargs).status_code == 401
    # Authenticated user without a staff/admin membership of this clinic
    assert getattr(client, method)(path, headers=auth("outsider"), **kwargs).status_code == 403
    assert audit_events == []
    assert _status(seeded, "a-flagged") == "needs_review"


# List / review queue

def test_list_returns_only_own_clinic(client, seeded, audit_events):  # noqa: F811
    response = client.get(A, headers=auth("staff-a"))

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert ids == {"a-flagged", "a-flagged-2", "a-normal", "a-reviewed"}
    assert "b-flagged" not in ids


def test_list_filters_by_review_status(client, seeded, audit_events):  # noqa: F811
    response = client.get(A, params={"review_status": "needs_review"}, headers=auth("admin-a"))

    assert response.status_code == 200
    rows = response.json()
    assert {r["id"] for r in rows} == {"a-flagged", "a-flagged-2"}
    assert {r["escalation_reason"] for r in rows} == {"emergency_signal", "low_confidence"}

    assert client.get(A, params={"review_status": "bogus"}, headers=auth("admin-a")).status_code == 422


def test_list_cross_clinic_denied(client, seeded, audit_events):  # noqa: F811
    # Clinic A staff cannot list clinic B, even by naming it in the path
    assert client.get(B, headers=auth("staff-a")).status_code == 403
    # Clinic B admin's own queue never contains clinic A records
    response = client.get(B, params={"review_status": "needs_review"}, headers=auth("admin-b"))
    assert [r["id"] for r in response.json()] == ["b-flagged"]


# Get single intake

def test_get_returns_owned_intake(client, seeded, audit_events):  # noqa: F811
    response = client.get(f"{A}/a-flagged", headers=auth("staff-a"))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "a-flagged"
    assert data["clinic_id"] == "default"
    assert data["review_status"] == "needs_review"
    assert data["escalation_reason"] == "emergency_signal"
    assert data["structured"]["clinical_structuring"]["confidence_level"] == 0.9
    assert data["report"]["report_sections"]["overview"] == "Pre-visit intake received."
    assert data["safety"]["severity"] == "low"


def test_get_cross_clinic_denied(client, seeded, audit_events):  # noqa: F811
    # Via another clinic's path: not a member
    assert client.get(f"{B}/b-flagged", headers=auth("staff-a")).status_code == 403
    # Via own clinic path with another clinic's intake id: indistinguishable from missing
    assert client.get(f"{A}/b-flagged", headers=auth("staff-a")).status_code == 404
    assert client.get(f"{A}/does-not-exist", headers=auth("staff-a")).status_code == 404
    assert audit_events == []


# Transitions

@pytest.mark.parametrize("target", ["reviewed", "escalated"])
def test_valid_transition_from_needs_review(client, seeded, audit_events, target):  # noqa: F811
    response = client.post(f"{A}/a-flagged/transition", json={"review_status": target}, headers=auth("staff-a"))

    assert response.status_code == 200
    assert response.json()["review_status"] == target
    assert response.json()["escalation_reason"] == "emergency_signal"
    assert _status(seeded, "a-flagged") == target


@pytest.mark.parametrize(
    "intake_id, target, code",
    [
        ("a-normal", "reviewed", 409),      # submitted is not in the review queue
        ("a-reviewed", "escalated", 409),   # already resolved
        ("a-flagged", "submitted", 422),    # not a staff transition target
        ("a-flagged", "needs_review", 422),
    ],
)
def test_invalid_transition_rejected(client, seeded, audit_events, intake_id, target, code):  # noqa: F811
    before = _status(seeded, intake_id)

    response = client.post(f"{A}/{intake_id}/transition", json={"review_status": target}, headers=auth("staff-a"))

    assert response.status_code == code
    assert _status(seeded, intake_id) == before
    assert audit_events == []


def test_transition_rejects_extra_fields(client, seeded, audit_events):  # noqa: F811
    response = client.post(
        f"{A}/a-flagged/transition",
        json={"review_status": "reviewed", "clinic_id": "clinic-b"},
        headers=auth("staff-a"),
    )
    assert response.status_code == 422
    assert _status(seeded, "a-flagged") == "needs_review"


def test_second_transition_is_rejected(client, seeded, audit_events):  # noqa: F811
    path = f"{A}/a-flagged/transition"
    assert client.post(path, json={"review_status": "reviewed"}, headers=auth("staff-a")).status_code == 200
    assert client.post(path, json={"review_status": "escalated"}, headers=auth("admin-a")).status_code == 409
    assert _status(seeded, "a-flagged") == "reviewed"


def test_transition_cross_clinic_denied(client, seeded, audit_events):  # noqa: F811
    body = {"review_status": "reviewed"}
    assert client.post(f"{B}/b-flagged/transition", json=body, headers=auth("staff-a")).status_code == 403
    assert client.post(f"{A}/b-flagged/transition", json=body, headers=auth("staff-a")).status_code == 404
    assert _status(seeded, "b-flagged") == "needs_review"
    assert audit_events == []


# Audit

def test_staff_actions_are_audited_with_actor_and_no_intake_text(client, seeded, audit_events):  # noqa: F811
    client.get(A, params={"review_status": "needs_review"}, headers=auth("staff-a"))
    client.get(f"{A}/a-flagged", headers=auth("staff-a"))
    client.post(f"{A}/a-flagged/transition", json={"review_status": "escalated"}, headers=auth("admin-a"))

    assert [(e.actor_id, e.action, e.resource_id) for e in audit_events] == [
        ("staff-a", "intake.list", None),
        ("staff-a", "intake.read", "a-flagged"),
        ("admin-a", "intake.transition", "a-flagged"),
    ]
    assert all(e.status == "success" and e.flags["clinic_id"] == "default" for e in audit_events)
    assert audit_events[0].flags["review_status"] == "needs_review"
    assert audit_events[0].flags["result_count"] == 2
    assert audit_events[2].flags["from_status"] == "needs_review"
    assert audit_events[2].flags["to_status"] == "escalated"

    serialized = json.dumps([e.__dict__ for e in audit_events])
    assert RAW_TEXT not in serialized
    assert "Pre-visit intake received." not in serialized
