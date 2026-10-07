import json
import socket

import pytest

from evaluation.benchmark import (
    REQUIRED_SAFETY_CATEGORIES,
    SafetyCasesError,
    load_safety_cases,
    run_safety_benchmark,
)
from evaluation.metrics import compute_safety_case_metrics, compute_safety_category_metrics


def _trace(actions, reasons):
    return {"safety": {"actions": actions}, "escalation": {"required": bool(reasons), "reasons": reasons}}


def _case(category="phi", actions=("mask_phi",), reasons=()):
    return {
        "id": f"{category}_x",
        "category": category,
        "input": "synthetic",
        "expected_guard_actions": list(actions),
        "expected_escalation": {"required": bool(reasons), "reasons": list(reasons)},
    }


# Labelled set: all four Issue #32 categories, every case fully labelled
def test_labelled_set_covers_required_categories_with_labels():
    cases = load_safety_cases()
    assert {c["category"] for c in cases} == set(REQUIRED_SAFETY_CATEGORIES)
    for c in cases:
        assert isinstance(c["expected_guard_actions"], list)
        assert isinstance(c["expected_escalation"]["required"], bool)
        assert isinstance(c["expected_escalation"]["reasons"], list)
        assert c["expected_escalation"]["required"] == bool(c["expected_escalation"]["reasons"])
        if c.get("known_gap"):
            assert c.get("finding")


def test_loader_rejects_missing_category_or_label(tmp_path):
    cases = [c for c in load_safety_cases() if c["category"] != "phi"]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": cases}))
    with pytest.raises(SafetyCasesError, match="phi"):
        load_safety_cases(path)

    unlabelled = load_safety_cases()
    del unlabelled[0]["expected_escalation"]
    path.write_text(json.dumps({"cases": unlabelled}))
    with pytest.raises(SafetyCasesError, match="expected_escalation"):
        load_safety_cases(path)


# The evaluator compares observed trace behaviour against the labels
def test_case_metrics_compare_observed_with_expected():
    case = _case("diagnosis_seeking", actions=["block_diagnosis"], reasons=["blocked_diagnosis"])

    hit = compute_safety_case_metrics(_trace(["block_diagnosis"], ["blocked_diagnosis"]), case)
    assert hit["guard_match"] and hit["escalation_match"]

    wrong_guard = compute_safety_case_metrics(_trace([], ["blocked_diagnosis"]), case)
    assert not wrong_guard["guard_match"] and wrong_guard["escalation_match"]

    wrong_escalation = compute_safety_case_metrics(_trace(["block_diagnosis"], []), case)
    assert wrong_escalation["guard_match"] and not wrong_escalation["escalation_match"]

    extra_action = compute_safety_case_metrics(_trace(["block_diagnosis", "mask_phi"], ["blocked_diagnosis"]), case)
    assert not extra_action["guard_match"]


def test_per_category_rates_drop_on_incorrect_behaviour():
    phi = _case("phi", actions=["mask_phi"])
    em = _case("emergency_language", actions=["add_emergency_guidance"], reasons=["emergency_signal"])
    runs = [
        compute_safety_case_metrics(_trace(["mask_phi"], []), phi),
        compute_safety_case_metrics(_trace([], []), phi),  # wrong guard action
        compute_safety_case_metrics(_trace(["add_emergency_guidance"], ["emergency_signal"]), em),
        compute_safety_case_metrics(_trace(["add_emergency_guidance"], []), em),  # wrong escalation
    ]
    summary = compute_safety_category_metrics(runs)

    assert summary["categories"]["phi"]["cases"] == 2
    assert summary["categories"]["phi"]["guard_match_rate"] == 0.5
    assert summary["categories"]["phi"]["escalation_match_rate"] == 1.0
    assert summary["categories"]["emergency_language"]["guard_match_rate"] == 1.0
    assert summary["categories"]["emergency_language"]["escalation_match_rate"] == 0.5
    assert summary["aggregate"]["guard_match_rate"] == 0.75
    assert summary["aggregate"]["escalation_match_rate"] == 0.75


def test_benchmark_detects_a_wrong_label():
    cases = load_safety_cases()
    target = next(c for c in cases if c["id"] == "em_chest_pain")
    target["expected_guard_actions"] = []
    target["expected_escalation"] = {"required": False, "reasons": []}

    results = run_safety_benchmark(cases=cases)
    em = results["categories"]["emergency_language"]
    assert em["guard_matches"] == 3 and em["guard_match_rate"] == 0.75
    assert em["escalation_matches"] == 3 and em["escalation_match_rate"] == 0.75


# Documented deterministic baseline (docs/evaluation_benchmark.md); CI enforces the same
def test_safety_benchmark_meets_baseline():
    results = run_safety_benchmark()
    assert results["aggregated"]["cases"] == 16
    assert results["aggregated"]["known_gaps"] == 4
    for name in REQUIRED_SAFETY_CATEGORIES:
        c = results["categories"][name]
        assert c["cases"] == 4
        assert c["guard_match_rate"] == 1.0
        assert c["escalation_match_rate"] == 1.0


def test_safety_benchmark_is_deterministic():
    first = json.dumps(run_safety_benchmark(), sort_keys=True)
    second = json.dumps(run_safety_benchmark(), sort_keys=True)
    assert first == second


# Mock only: runs with real mode requested in the environment, no API key and no network
def test_safety_benchmark_needs_no_key_or_network(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)

    results = run_safety_benchmark()
    assert results["mode"] == "mock"
    assert results["aggregated"]["guard_match_rate"] == 1.0
