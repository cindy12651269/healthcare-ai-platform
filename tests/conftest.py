# Hermetic test settings: never read the developer's local .env (which may set LLM_MODE=real
# and a real OPENAI_API_KEY), and start every test with a fresh settings cache.
import pytest

from api.config import Settings, get_settings

Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
