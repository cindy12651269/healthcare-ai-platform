# Hermetic test settings: never read the developer's local .env (which may set LLM_MODE=real
# and a real OPENAI_API_KEY), start every test with a fresh settings cache, and write audit
# JSONL events to a per-test temporary file instead of ./audit.jsonl.
import pytest

from api.config import Settings, get_settings

Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True)
def _isolated_audit_log(tmp_path, monkeypatch):
    monkeypatch.setattr("observability.audit_logger.JSONL_PATH", str(tmp_path / "audit.jsonl"))


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
