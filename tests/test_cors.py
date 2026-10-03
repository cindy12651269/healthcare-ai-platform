from fastapi.testclient import TestClient
from api.main import app
from api.config import Settings

client = TestClient(app)

ALLOWED = "http://localhost:3000"
DISALLOWED = "http://evil.example.com"


def _preflight(origin: str):
    return client.options(
        "/api/ingest",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )


# Preflight from the local Next.js origin is allowed
def test_preflight_allowed_origin():
    response = _preflight(ALLOWED)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in response.headers


# Preflight from an unlisted origin is rejected (no wildcard)
def test_preflight_disallowed_origin():
    response = _preflight(DISALLOWED)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


# Simple request from an unlisted origin gets no CORS allow header
def test_simple_request_disallowed_origin():
    response = client.get("/health", headers={"Origin": DISALLOWED})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


# Allowed origins are configurable via a comma-separated setting
def test_cors_origins_parsed_from_setting():
    settings = Settings(cors_allowed_origins=" http://a.test , http://b.test,, ")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
