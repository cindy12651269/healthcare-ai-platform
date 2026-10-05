# Issue #22: configurable LLM mode, shared provider interface, OpenAI wrapper failure handling.
# No test here makes a real network call: the OpenAI client is always a fake.
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError, AuthenticationError, InternalServerError
from pydantic import ValidationError

from agents.output_agent import OutputAgent
from agents.structuring_agent import SchemaValidationError, StructuringAgent
from api.config import Settings, get_settings
from evaluation.benchmark import create_pipeline, run_benchmark
from llm.provider import (
    LLMConfigurationError,
    LLMMalformedOutputError,
    LLMProviderError,
    LLMTimeoutError,
    check_llm_config,
)
from llm.providers.openai_client import OpenAIProvider

REQ = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
SECRET = "sk-test-SECRET-should-never-leak"


def _response(content):
    msg = type("M", (), {"content": content})()
    choice = type("C", (), {"message": msg})()
    return type("R", (), {"choices": [choice]})()


class FakeClient:
    """Plays back a script of exceptions / response contents and records calls."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _response(item)


def _provider(script, max_retries=2):
    client = FakeClient(script)
    provider = OpenAIProvider(
        api_key=SECRET, model="gpt-test", timeout=5, max_retries=max_retries,
        client=client, sleep=lambda s: None,
    )
    return provider, client


def _call(provider):
    return provider.generate_json(system="s", prompt="p", context={})


# Mode configuration

def test_default_mode_is_mock():
    assert Settings().llm_mode == "mock"
    assert StructuringAgent().provider.name == "mock"
    assert OutputAgent().provider.name == "mock"


def test_invalid_mode_fails_explicitly(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "bogus")
    with pytest.raises(ValidationError, match="Unsupported LLM_MODE"):
        Settings()
    with pytest.raises(LLMConfigurationError):
        StructuringAgent(mode="bogus")


def test_mock_mode_needs_no_key(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    check_llm_config(Settings())  # does not raise


def test_real_mode_without_key_fails_without_fallback(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        check_llm_config(Settings())
    with pytest.raises(LLMConfigurationError):
        StructuringAgent()
    with pytest.raises(LLMConfigurationError):
        OutputAgent()


def test_real_benchmark_refuses_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError):
        create_pipeline(mode="real", rag_enabled=False)


def test_mock_benchmark_is_deterministic_and_labelled():
    a, b = run_benchmark(mode="mock", rag=False), run_benchmark(mode="mock", rag=False)
    assert a["mode"] == "mock"
    assert a == b


# OpenAI provider wrapper

def test_provider_returns_json_object_and_sets_timeout():
    provider, client = _provider(['{"ok": true}'])
    assert _call(provider) == {"ok": True}
    assert client.calls[0]["timeout"] == 5
    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_transient_failure_is_retried_then_succeeds():
    err = InternalServerError("boom", response=httpx.Response(500, request=REQ), body=None)
    provider, client = _provider([err, '{"ok": 1}'])
    assert _call(provider) == {"ok": 1}
    assert len(client.calls) == 2


def test_timeout_retries_are_bounded():
    provider, client = _provider([APITimeoutError(request=REQ)] * 3, max_retries=2)
    with pytest.raises(LLMTimeoutError):
        _call(provider)
    assert len(client.calls) == 3


def test_provider_error_is_not_retried_and_sanitized():
    err = AuthenticationError(
        f"Incorrect API key provided: {SECRET}",
        response=httpx.Response(401, request=REQ),
        body={"error": {"message": SECRET}},
    )
    provider, client = _provider([err])
    with pytest.raises(LLMProviderError) as exc_info:
        _call(provider)
    assert len(client.calls) == 1
    assert "401" in str(exc_info.value)
    assert SECRET not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


@pytest.mark.parametrize("content", ["not json", "[1, 2]", None])
def test_malformed_output_is_controlled_failure(content):
    provider, client = _provider([content])
    with pytest.raises(LLMMalformedOutputError):
        _call(provider)
    assert len(client.calls) == 1


# Agents keep their interfaces and validate schemas in real mode

def test_structuring_agent_real_mode_rejects_schema_invalid_output():
    provider, _ = _provider([json.dumps({"trace": {}})])
    agent = StructuringAgent(mode="real", provider=provider)
    with pytest.raises(SchemaValidationError):
        agent.run({"input_id": "x", "raw_text": "headache"})


def test_output_agent_real_mode_rejects_schema_invalid_output():
    provider, _ = _provider([json.dumps({"report_sections": {}})])
    agent = OutputAgent(mode="real", provider=provider)
    with pytest.raises(ValueError, match="schema validation failed"):
        agent.run(structured_data={"trace": {}}, retrieval_context=None)


def test_agents_real_mode_through_shared_interface():
    intake = {
        "input_id": "id-1", "user_id": "u", "timestamp": "2025-01-01T00:00:00Z",
        "source": "web", "input_type": "intake", "raw_text": "Mild headache for two days.",
        "contains_phi": False, "consent_granted": True,
    }
    mock_structured = StructuringAgent(mode="mock").run(intake)
    mock_structured.pop("safety_violation_count")
    s_provider, s_client = _provider([json.dumps(mock_structured)])
    structured = StructuringAgent(mode="real", provider=s_provider).run(intake)
    assert structured["output_metadata"]["model_version"] == "gpt-test"
    assert "Mild headache" in s_client.calls[0]["messages"][1]["content"]

    mock_report = OutputAgent(mode="mock").run(structured)["report"]
    mock_report.pop("safety_checks")
    o_provider, _ = _provider([json.dumps(mock_report)])
    result = OutputAgent(mode="real", provider=o_provider).run(structured_data=structured, retrieval_context=None)
    assert set(result) == {"report", "_safety"}
    assert result["report"]["report_metadata"]["model_version"] == "gpt-test"


# Health endpoint

def test_health_reports_only_execution_mode():
    from api.main import app

    body = TestClient(app).get("/health").json()
    assert body["llm_mode"] == get_settings().llm_mode == "mock"
    assert not any("key" in k.lower() or "openai" in k.lower() for k in body)


def test_ingest_maps_provider_failure_to_502_without_fallback(monkeypatch):
    from agents.pipeline import HealthcarePipeline
    from api.deps import get_pipeline
    from api.main import app

    monkeypatch.setattr(get_settings(), "enable_persistence", False)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda e: None)
    monkeypatch.setattr("agents.pipeline.log_run", lambda e: None)
    provider, _ = _provider([APITimeoutError(request=REQ)] * 3)
    pipeline = HealthcarePipeline(structuring_agent=StructuringAgent(mode="real", provider=provider))
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    try:
        resp = TestClient(app).post(
            "/api/ingest", json={"text": "Mild headache for two days.", "consent_granted": True}
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 502
    assert "timed out" in resp.json()["detail"]
    assert SECRET not in resp.text


# Real-mode schema contract (post-merge fix): strict JSON-schema output, optional nulls, controlled failures

from pathlib import Path

from agents.output_agent import ReportSchemaValidationError
from agents.structuring_agent import load_structured_schema


def load_report_schema():
    return json.loads((Path(__file__).resolve().parent.parent / "llm/schemas/report_output.json").read_text())
from llm.providers.openai_client import strip_optional_nulls, to_strict_schema

INTAKE = {
    "input_id": "id-1", "user_id": "u", "timestamp": "2025-01-01T00:00:00Z",
    "source": "web", "input_type": "intake", "raw_text": "Mild headache for two days.",
    "contains_phi": False, "consent_granted": True,
}


def _walk_objects(node):
    for alt in node.get("anyOf", []):
        yield from _walk_objects(alt)
    if node.get("type") == "object":
        yield node
        for sub in node["properties"].values():
            yield from _walk_objects(sub)
    if isinstance(node.get("items"), dict):
        yield from _walk_objects(node["items"])


@pytest.mark.parametrize("loader", [load_structured_schema, load_report_schema])
def test_strict_schema_meets_openai_strict_rules(loader):
    strict = to_strict_schema(loader())
    assert "$schema" not in strict
    assert "maxLength" not in json.dumps(strict)
    objects = list(_walk_objects(strict))
    assert objects
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"])


def test_strict_schema_makes_only_optional_fields_nullable():
    clinical = to_strict_schema(load_structured_schema())["properties"]["clinical_structuring"]["properties"]
    assert clinical["severity"]["type"] == ["string", "null"]
    assert clinical["symptoms"]["type"] == "array"  # required in the domain schema: stays non-null
    assert {"type": "null"} in clinical["red_flags"]["anyOf"]  # optional array
    sync = to_strict_schema(load_structured_schema())["properties"]["ehr_interoperability"]["properties"]["sync_status"]
    assert None in sync["enum"]


def test_both_agents_send_their_schema_as_strict_response_format():
    structured = StructuringAgent(mode="mock").run(INTAKE)
    structured.pop("safety_violation_count")
    s_provider, s_client = _provider([json.dumps(structured)])
    StructuringAgent(mode="real", provider=s_provider).run(INTAKE)
    fmt = s_client.calls[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"] == to_strict_schema(load_structured_schema())

    report = OutputAgent(mode="mock").run(structured)["report"]
    o_provider, o_client = _provider([json.dumps(report)])
    OutputAgent(mode="real", provider=o_provider).run(structured_data=structured)
    fmt = o_client.calls[0]["response_format"]
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"] == to_strict_schema(load_report_schema())


def test_severity_null_from_provider_is_treated_as_absent():
    # Reproduces the smoke-test failure: the model returned clinical_structuring.severity = null
    structured = StructuringAgent(mode="mock").run(INTAKE)
    structured.pop("safety_violation_count")
    structured["clinical_structuring"].update(severity=None, duration=None, onset=None, red_flags=None)
    structured["ehr_interoperability"] = {"patient_id": None, "sync_status": None}
    provider, _ = _provider([json.dumps(structured)])
    result = StructuringAgent(mode="real", provider=provider).run(INTAKE)
    assert "severity" not in result["clinical_structuring"]
    assert "red_flags" not in result["clinical_structuring"]
    assert result["ehr_interoperability"] == {}


def test_null_in_required_field_still_fails_validation():
    structured = StructuringAgent(mode="mock").run(INTAKE)
    structured.pop("safety_violation_count")
    structured["clinical_structuring"]["clinical_summary"] = None
    provider, _ = _provider([json.dumps(structured)])
    with pytest.raises(SchemaValidationError, match="clinical_structuring/clinical_summary"):
        StructuringAgent(mode="real", provider=provider).run(INTAKE)


def test_strip_optional_nulls_recurses_into_arrays():
    schema = {"type": "object", "properties": {"xs": {"type": "array", "items": {
        "type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}, "required": ["a"]}}}}
    assert strip_optional_nulls({"xs": [{"a": None, "b": None}]}, schema) == {"xs": [{"a": None}]}


def test_report_schema_failure_is_controlled_and_does_not_echo_output():
    provider, _ = _provider([json.dumps({"report_sections": {"overview": "SENSITIVE-TEXT"}})])
    with pytest.raises(ReportSchemaValidationError) as exc_info:
        OutputAgent(mode="real", provider=provider).run(structured_data={"trace": {}})
    assert "SENSITIVE-TEXT" not in str(exc_info.value)


def test_ingest_maps_structuring_and_report_schema_failures_to_422(monkeypatch):
    from agents.pipeline import HealthcarePipeline
    from api.deps import get_pipeline
    from api.main import app

    monkeypatch.setattr(get_settings(), "enable_persistence", False)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda e: None)
    monkeypatch.setattr("agents.pipeline.log_run", lambda e: None)

    bad_struct, _ = _provider([json.dumps({"trace": {}})])
    bad_report, _ = _provider([json.dumps({"report_sections": {}})])
    pipelines = [
        HealthcarePipeline(structuring_agent=StructuringAgent(mode="real", provider=bad_struct)),
        HealthcarePipeline(output_agent=OutputAgent(mode="real", provider=bad_report)),
    ]
    try:
        for pipeline, prefix in zip(pipelines, ["LLM structuring error", "LLM report error"]):
            app.dependency_overrides[get_pipeline] = lambda p=pipeline: p
            resp = TestClient(app).post(
                "/api/ingest", json={"text": "Mild headache for two days.", "consent_granted": True}
            )
            assert resp.status_code == 422
            assert resp.json()["detail"].startswith(prefix)
    finally:
        app.dependency_overrides.clear()
