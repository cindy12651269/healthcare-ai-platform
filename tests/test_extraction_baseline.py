"""Issue #40: deterministic rule-based extraction baseline and extraction metrics."""
import json
import socket

import jsonschema
import pytest

from agents.escalation import LOW_CONFIDENCE_THRESHOLD, evaluate_escalation
from agents.extraction_baseline import EXTRACTION_METHOD, extract
from agents.structuring_agent import StructuringAgent, load_structured_schema
from evaluation.benchmark import run_extraction_benchmark
from evaluation.metrics import compute_aggregate_symptom_metrics, compute_symptom_metrics

ROUTINE = "I have had a sore throat and a mild fever for two days."
VAGUE = "I just don't feel right and wanted to check in."


def _structure(text):
    return StructuringAgent(mode="mock").run({
        "input_id": "t1", "user_id": "u1", "source": "web", "input_type": "chat",
        "timestamp": "2025-01-01T00:00:00Z", "raw_text": text,
    })


def test_routine_intake_extracts_stated_fields():
    clinical = _structure(ROUTINE)["clinical_structuring"]
    assert clinical["symptoms"] == ["sore throat", "fever"]
    assert clinical["duration"] == "two days"
    assert clinical["severity"] == "mild"
    assert clinical["red_flags"] == []
    assert "onset" not in clinical  # not stated, not invented
    assert clinical["confidence_level"] >= LOW_CONFIDENCE_THRESHOLD
    assert "not LLM-generated" in clinical["clinical_summary"]
    assert "sore throat, fever" in clinical["clinical_summary"]


def test_onset_red_flags_and_severity():
    f = extract("Severe chest pain and shortness of breath since this morning.")
    assert f["symptoms"] == ["chest pain", "shortness of breath"]
    assert f["red_flags"] == ["chest pain", "shortness of breath"]
    assert f["onset"] == "since this morning"
    assert f["severity"] == "severe"
    assert f["confidence_level"] == 1.0


def test_negated_symptom_is_not_extracted():
    assert extract("I have a cough but no fever.")["symptoms"] == ["cough"]


def test_vague_intake_is_low_confidence_and_escalated():
    structured = _structure(VAGUE)
    clinical = structured["clinical_structuring"]
    assert clinical["symptoms"] == []
    assert clinical["confidence_level"] < LOW_CONFIDENCE_THRESHOLD
    decision = evaluate_escalation(intake_text=VAGUE, structured=structured, safety_actions=[])
    assert decision["required"] is True
    assert decision["reasons"] == ["low_confidence"]


@pytest.mark.parametrize("text,expected", [
    ("", 0.1),
    ("I have a cough.", 0.5),  # exactly at threshold: not escalated (strict <)
    ("I have a cough and a fever.", 0.65),
    ("I have a mild cough and a fever for two days.", 1.0),
])
def test_confidence_formula(text, expected):
    assert extract(text)["confidence_level"] == expected


def test_mock_output_is_deterministic_and_schema_valid():
    first, second = _structure(ROUTINE), _structure(ROUTINE)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    structured = {k: v for k, v in first.items() if k != "safety_violation_count"}
    jsonschema.validate(structured, load_structured_schema())
    assert first["output_metadata"]["model_version"] == "mock"
    assert first["output_metadata"]["prompt_version"] == EXTRACTION_METHOD


def test_symptom_metrics_per_run():
    m = compute_symptom_metrics(["Fever", "rash"], ["fever", "cough"])
    assert (m["true_positives"], m["false_positives"], m["false_negatives"]) == (1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5
    assert compute_symptom_metrics([], [])["precision"] == 1.0


def test_symptom_metrics_aggregate():
    runs = [compute_symptom_metrics(["fever"], ["fever", "cough"]), compute_symptom_metrics(["rash"], ["rash"])]
    a = compute_aggregate_symptom_metrics(runs)
    assert a["micro_precision"] == 1.0
    assert a["micro_recall"] == pytest.approx(2 / 3)
    assert a["macro_recall"] == pytest.approx(0.75)


def test_extraction_benchmark_mock_is_deterministic_without_key_or_network(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", no_network)
    first = run_extraction_benchmark("mock")
    assert json.dumps(first, sort_keys=True) == json.dumps(run_extraction_benchmark("mock"), sort_keys=True)
    assert first["extraction_method"] == "deterministic_rule_based_baseline"
    assert len(first["runs"]) == first["aggregated"]["cases"] > 0
    assert {"precision", "recall"} <= set(first["runs"][0])
