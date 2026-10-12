# Guided demo seed (Issue #43): deterministic synthetic intakes in two clinics covering every
# review status, idempotent, clinic-isolated, and only seeded when APP_ENV=demo.
import os
import subprocess
import sys

from fastapi.testclient import TestClient

from api.auth import issue_token
from api.config import get_settings
from api.main import app
from db.models import REVIEW_STATUSES, HealthRecord, ReviewEvent, WebhookDelivery
from db.seed_demo import DEMO_INTAKES, seed_demo
from tests.test_deploy_demo import AUTH_SECRET, sessions  # noqa: F401  (pytest fixture)


def _seed(sessions):  # noqa: F811
    with sessions() as s:
        created = seed_demo(s)
        s.commit()
    return created


def test_seed_covers_every_status_in_two_clinics_and_is_idempotent(sessions):  # noqa: F811
    first = _seed(sessions)
    assert sum(c.startswith("intake ") for c in first) == len(DEMO_INTAKES) == 8
    assert _seed(sessions) == []  # second run creates nothing

    with sessions() as s:
        records = s.query(HealthRecord).all()
        assert len(records) == 8 and len({r.id for r in records}) == 8
        by_clinic = {}
        for r in records:
            by_clinic.setdefault(r.clinic_id, set()).add(r.review_status)
        assert by_clinic == {"default": set(REVIEW_STATUSES), "demo-clinic-b": set(REVIEW_STATUSES)}
        # Escalation reasons come from the pipeline itself
        reasons = {r.id: r.escalation_reason for r in records}
        assert reasons["demo-intake-a1"] is None
        assert reasons["demo-intake-a2"] == "emergency_signal"
        assert "low_confidence" in reasons["demo-intake-a3"]
        assert "blocked_prescription" in reasons["demo-intake-a4"]
        # Resolved intakes carry one recorded transition each, by a member of the owning clinic
        events = {(e.intake_id, e.clinic_id, e.actor_id, e.from_status, e.to_status) for e in s.query(ReviewEvent)}
        assert events == {
            ("demo-intake-a3", "default", "demo-staff-a", "needs_review", "reviewed"),
            ("demo-intake-a4", "default", "demo-admin-a", "needs_review", "escalated"),
            ("demo-intake-b3", "demo-clinic-b", "demo-admin-b", "needs_review", "escalated"),
            ("demo-intake-b4", "demo-clinic-b", "demo-admin-b", "needs_review", "reviewed"),
        }
        assert s.query(WebhookDelivery).count() == 0  # seeding never notifies


def test_each_clinic_sees_only_its_own_seeded_intakes(sessions, monkeypatch):  # noqa: F811
    monkeypatch.setattr(get_settings(), "auth_token_secret", AUTH_SECRET)
    _seed(sessions)
    client = TestClient(app)
    staff_a = {"Authorization": f"Bearer {issue_token('demo-staff-a', 600)}"}
    admin_b = {"Authorization": f"Bearer {issue_token('demo-admin-b', 600)}"}

    a = client.get("/api/clinics/default/intakes", headers=staff_a).json()
    b = client.get("/api/clinics/demo-clinic-b/intakes", headers=admin_b).json()
    assert {r["id"] for r in a} == {i[0] for i in DEMO_INTAKES if i[1] == "default"}
    assert {r["id"] for r in b} == {i[0] for i in DEMO_INTAKES if i[1] == "demo-clinic-b"}
    assert client.get("/api/clinics/demo-clinic-b/intakes", headers=staff_a).status_code == 403
    assert client.get("/api/clinics/default/intakes/demo-intake-b1", headers=staff_a).status_code == 404
    assert client.get("/api/clinics/default/intakes/demo-intake-a1/timeline", headers=admin_b).status_code == 403


def test_cli_refuses_outside_demo_environment():
    env = {k: v for k, v in os.environ.items() if k != "APP_ENV"}
    env["DATABASE_URL"] = "sqlite://"  # never reached
    result = subprocess.run([sys.executable, "-m", "db.seed_demo"], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "APP_ENV is not 'demo'" in result.stderr


# The four UI scenario presets (app/services/demo.ts) behave as their labels claim, through the real pipeline
def test_scenario_presets_produce_the_documented_outcomes(monkeypatch):
    import re
    from pathlib import Path

    from agents.output_agent import OutputAgent
    from agents.pipeline import HealthcarePipeline
    from agents.structuring_agent import StructuringAgent

    source = (Path(__file__).resolve().parent.parent / "app" / "services" / "demo.ts").read_text(encoding="utf-8")
    presets = dict(re.findall(r'id: "(\w+)",\s*label: "[^"]+",\s*text: "([^"]+)"', source))
    assert set(presets) == {"routine", "emergency", "prescription", "vague"}

    pipeline = HealthcarePipeline(structuring_agent=StructuringAgent(mode="mock"), output_agent=OutputAgent(mode="mock"),
                                  retrieval_agent=None, enable_retrieval=False)
    outcome = {}
    for pid, text in presets.items():
        trace = pipeline.run(raw_text=text, meta={"source": "web", "input_type": "chat", "consent_granted": True},
                             enable_rag=False, persistence_enabled=False)
        outcome[pid] = (trace["escalation"]["review_status"], trace["escalation"]["reasons"])
    assert outcome == {
        "routine": ("submitted", []),
        "emergency": ("needs_review", ["emergency_signal"]),
        "prescription": ("needs_review", ["blocked_prescription"]),
        "vague": ("needs_review", ["low_confidence"]),
    }
