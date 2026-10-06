# Staff authentication, RBAC and clinic isolation (Issue #28) on SQLite.
# PostgreSQL coverage of the same endpoints is in tests/test_persistence_postgres.py.
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import InvalidToken, issue_token, verify_token
from api.config import get_settings
from api.deps import get_pipeline
from api.main import app
from db.models import Base, Clinic, ClinicMembership, HealthRecord, User
from db.session import get_db

SECRET = "test-secret-" + "x" * 40


@pytest.fixture
def sessions(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as s:
        s.add_all([Clinic(id="default", name="Clinic A"), Clinic(id="clinic-b", name="Clinic B")])
        s.add_all([
            User(id="staff-a", email="staff-a@example.test"),
            User(id="admin-a", email="admin-a@example.test"),
            User(id="admin-b", email="admin-b@example.test"),
            User(id="outsider", email="outsider@example.test"),
            User(id="new-user", email="new@example.test"),
        ])
        s.flush()
        s.add_all([
            ClinicMembership(user_id="staff-a", clinic_id="default", role="clinic_staff"),
            ClinicMembership(user_id="admin-a", clinic_id="default", role="clinic_admin"),
            ClinicMembership(user_id="admin-b", clinic_id="clinic-b", role="clinic_admin"),
        ])
        s.commit()

    def _get_db():
        db = Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(get_settings(), "auth_token_secret", SECRET)
    app.dependency_overrides[get_db] = _get_db
    yield Session
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


@pytest.fixture
def client(sessions):
    return TestClient(app)


def auth(user_id, ttl=3600):
    return {"Authorization": f"Bearer {issue_token(user_id, ttl)}"}


def membership(Session, user_id, clinic_id):
    with Session() as s:
        m = s.get(ClinicMembership, (user_id, clinic_id))
        return m.role if m else None


# Tokens

def test_token_round_trip_and_tampering(sessions):
    token = issue_token("staff-a", 60)
    assert verify_token(token) == "staff-a"

    version, body, signature = token.split(".")
    forged_body = issue_token("admin-a", 60).split(".")[1]
    for bad in (f"{version}.{forged_body}.{signature}", token + "x", "not-a-token", f"v2.{body}.{signature}"):
        with pytest.raises(InvalidToken):
            verify_token(bad)

    with pytest.raises(InvalidToken, match="expired"):
        verify_token(issue_token("staff-a", -1))


# Authentication (401)

@pytest.mark.parametrize("path", ["/api/staff/me", "/api/clinics/default/members"])
def test_missing_authentication_is_401(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_authentication_is_401(client, sessions, monkeypatch):
    expired = issue_token("staff-a", -1)
    unknown_user = issue_token("no-such-user", 3600)
    monkeypatch.setattr(get_settings(), "auth_token_secret", "another-secret-" + "y" * 40)
    wrong_key = issue_token("staff-a", 3600)
    monkeypatch.setattr(get_settings(), "auth_token_secret", SECRET)

    for header in (
        f"Bearer {expired}",
        f"Bearer {unknown_user}",
        f"Bearer {wrong_key}",
        "Bearer garbage",
        f"Basic {issue_token('staff-a', 3600)}",
    ):
        response = client.get("/api/clinics/default/members", headers={"Authorization": header})
        assert response.status_code == 401, header


def test_non_ascii_signature_is_401_not_500(sessions):
    version, body, _ = issue_token("staff-a", 3600).split(".")
    client = TestClient(app, raise_server_exceptions=False)
    # Raw latin-1 header bytes: the server sees a signature of non-ASCII characters
    header = f"Bearer {version}.{body}.\u00e9\u00e9".encode("latin-1")
    response = client.get("/api/staff/me", headers=[(b"authorization", header)])
    assert response.status_code == 401
    with pytest.raises(InvalidToken):
        verify_token(f"{version}.{body}.\u00e9\u00e9")


def test_staff_endpoints_unavailable_without_secret(client, monkeypatch):
    token = issue_token("staff-a", 3600)
    monkeypatch.setattr(get_settings(), "auth_token_secret", None)
    response = client.get("/api/staff/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503


def test_me_returns_memberships_from_database(client):
    response = client.get("/api/staff/me", headers=auth("admin-a"))
    assert response.status_code == 200
    assert response.json() == {
        "user_id": "admin-a",
        "email": "admin-a@example.test",
        "memberships": [{"clinic_id": "default", "role": "clinic_admin"}],
    }


# RBAC (403)

def test_staff_can_read_own_clinic_members(client):
    response = client.get("/api/clinics/default/members", headers=auth("staff-a"))
    assert response.status_code == 200
    assert {m["user_id"]: m["role"] for m in response.json()} == {
        "admin-a": "clinic_admin",
        "staff-a": "clinic_staff",
    }


def test_staff_cannot_manage_members(client, sessions):
    put = client.put("/api/clinics/default/members/new-user", json={"role": "clinic_staff"}, headers=auth("staff-a"))
    delete = client.delete("/api/clinics/default/members/admin-a", headers=auth("staff-a"))

    assert (put.status_code, delete.status_code) == (403, 403)
    assert membership(sessions, "new-user", "default") is None
    assert membership(sessions, "admin-a", "default") == "clinic_admin"


def test_admin_manages_own_clinic_members(client, sessions):
    grant = client.put("/api/clinics/default/members/new-user", json={"role": "clinic_staff"}, headers=auth("admin-a"))
    assert grant.status_code == 200
    assert grant.json() == {"user_id": "new-user", "email": "new@example.test", "role": "clinic_staff"}
    assert membership(sessions, "new-user", "default") == "clinic_staff"

    promote = client.put("/api/clinics/default/members/new-user", json={"role": "clinic_admin"}, headers=auth("admin-a"))
    assert promote.status_code == 200
    assert membership(sessions, "new-user", "default") == "clinic_admin"

    remove = client.delete("/api/clinics/default/members/new-user", headers=auth("admin-a"))
    assert remove.status_code == 204
    assert membership(sessions, "new-user", "default") is None


def test_admin_input_errors(client):
    headers = auth("admin-a")
    assert client.put("/api/clinics/default/members/no-such-user", json={"role": "clinic_staff"}, headers=headers).status_code == 404
    assert client.put("/api/clinics/default/members/new-user", json={"role": "owner"}, headers=headers).status_code == 422
    assert client.delete("/api/clinics/default/members/new-user", headers=headers).status_code == 404
    # No self-demotion / self-removal (clinic lock-out)
    assert client.put("/api/clinics/default/members/admin-a", json={"role": "clinic_staff"}, headers=headers).status_code == 409
    assert client.delete("/api/clinics/default/members/admin-a", headers=headers).status_code == 409


def test_removed_membership_takes_effect_immediately(client):
    staff = auth("staff-a")
    assert client.get("/api/clinics/default/members", headers=staff).status_code == 200
    assert client.delete("/api/clinics/default/members/staff-a", headers=auth("admin-a")).status_code == 204
    assert client.get("/api/clinics/default/members", headers=staff).status_code == 403


# Clinic isolation

@pytest.mark.parametrize("user_id", ["staff-a", "admin-a", "outsider"])
def test_cross_clinic_read_is_denied(client, user_id):
    response = client.get("/api/clinics/clinic-b/members", headers=auth(user_id))
    assert response.status_code == 403


def test_admin_cannot_manage_another_clinic(client, sessions):
    headers = auth("admin-a")
    grant = client.put("/api/clinics/clinic-b/members/new-user", json={"role": "clinic_admin"}, headers=headers)
    self_grant = client.put("/api/clinics/clinic-b/members/admin-a", json={"role": "clinic_admin"}, headers=headers)
    remove = client.delete("/api/clinics/clinic-b/members/admin-b", headers=headers)

    assert (grant.status_code, self_grant.status_code, remove.status_code) == (403, 403, 403)
    assert membership(sessions, "new-user", "clinic-b") is None
    assert membership(sessions, "admin-a", "clinic-b") is None
    assert membership(sessions, "admin-b", "clinic-b") == "clinic_admin"


def test_client_supplied_clinic_id_cannot_bypass_isolation(client, sessions):
    headers = auth("admin-a")
    # A clinic id in the query or body never replaces the authorized path clinic
    assert client.get("/api/clinics/clinic-b/members?clinic_id=default", headers=headers).status_code == 403
    assert client.put(
        "/api/clinics/clinic-b/members/new-user",
        json={"role": "clinic_staff", "clinic_id": "default"},
        headers=headers,
    ).status_code == 403
    # On the admin's own clinic, an extra clinic_id field is rejected rather than honoured
    assert client.put(
        "/api/clinics/default/members/new-user",
        json={"role": "clinic_staff", "clinic_id": "clinic-b"},
        headers=headers,
    ).status_code == 422
    assert membership(sessions, "new-user", "clinic-b") is None
    assert membership(sessions, "new-user", "default") is None


# Patient intake is unchanged

def test_ingest_stays_unauthenticated_and_uses_default_clinic(client, sessions, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.setattr(get_settings(), "enable_persistence", True)
    monkeypatch.setattr("agents.pipeline.SessionLocal", sessions)
    monkeypatch.setattr("api.middleware.audit.log_run", lambda event: None)
    get_pipeline.cache_clear()
    try:
        response = client.post(
            "/api/ingest",
            json={
                "text": "I have had a sore throat for two days.",
                "consent_granted": True,
                "source": "web",
                "input_type": "intake",
                "clinic_id": "clinic-b",  # ignored: ingest never takes a clinic from the client
            },
        )
        phi_without_consent = client.post(
            "/api/ingest",
            json={"text": "My phone is 555-123-4567 and I have a cough.", "consent_granted": False},
        )
    finally:
        get_pipeline.cache_clear()

    assert response.status_code == 200
    assert response.json()["persistence"]["status"] == "saved"
    with sessions() as s:
        record = s.get(HealthRecord, response.json()["persistence"]["record_id"])
        assert record.clinic_id == "default"
    assert phi_without_consent.status_code == 400  # consent gate unchanged
