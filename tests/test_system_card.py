# System card (Issue #43): public read-only data, kept in sync with current deterministic behaviour.
from fastapi.testclient import TestClient

from agents.escalation import LOW_CONFIDENCE_THRESHOLD
from api.main import app
from evaluation.system_card import build_results, load_results


def test_committed_snapshot_matches_current_evaluation_results():
    # Fails when guard/escalation/extraction behaviour changes without regenerating the snapshot
    assert load_results() == build_results()


def test_system_card_endpoint_serves_committed_results_and_rules(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "mock")
    body = TestClient(app).get("/api/system-card").json()

    assert body["evaluation"] == load_results()
    assert body["execution_mode"] == "mock"
    assert body["low_confidence_threshold"] == LOW_CONFIDENCE_THRESHOLD == 0.5
    assert {r["reason"] for r in body["escalation_rules"]} == {
        "emergency_signal", "blocked_diagnosis", "blocked_prescription", "low_confidence"}
    assert {r["action"] for r in body["safety_rules"]} == {
        "block_diagnosis", "block_prescription", "add_emergency_guidance", "mask_phi"}
    assert body["not_a_medical_device"].startswith("Not a medical device")
    assert "in-sample" in body["evaluation"]["extraction"]["limitation"].lower()


def test_documented_numbers_match_snapshot():
    from pathlib import Path
    doc = (Path(__file__).resolve().parent.parent / "docs" / "evaluation_benchmark.md").read_text(encoding="utf-8")
    agg = load_results()["safety_escalation"]["aggregate"]
    assert f"| **Total** | **{agg['cases']}** | **{agg['guard_matches']}** | **{agg['guard_match_rate']:.2f}** | " \
           f"**{agg['escalation_matches']}** | **{agg['escalation_match_rate']:.2f}** | **{agg['known_gaps']}** |" in doc
