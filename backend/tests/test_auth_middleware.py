from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from councilsense.app.main import create_app


def _b64url(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _issue_token(user_id: str, *, secret: str, expires_in_seconds: int) -> str:
    header = _b64url({"alg": "HS256", "typ": "JWT"})
    exp = int((datetime.now(tz=UTC) + timedelta(seconds=expires_in_seconds)).timestamp())
    payload = _b64url({"sub": user_id, "exp": exp})
    signing_input = f"{header}.{payload}"
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
    return f"{signing_input}.{signature}"


def _client_with_secret(monkeypatch, secret: str) -> TestClient:
    monkeypatch.setenv("AUTH_SESSION_SECRET", secret)
    return TestClient(create_app())


def test_rejects_unauthenticated_requests_with_consistent_contract(monkeypatch):
    client = _client_with_secret(monkeypatch, "test-secret")

    me_response = client.get("/v1/me")
    bootstrap_response = client.get("/v1/me/bootstrap")

    expected = {
        "error": {
            "code": "unauthorized",
            "message": "Authentication required",
        }
    }
    assert me_response.status_code == 401
    assert bootstrap_response.status_code == 401
    assert me_response.json() == expected
    assert bootstrap_response.json() == expected


def test_rejects_expired_session(monkeypatch):
    secret = "test-secret"
    client = _client_with_secret(monkeypatch, secret)
    token = _issue_token("user-123", secret=secret, expires_in_seconds=-10)

    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_injects_authenticated_identity_into_protected_routes(monkeypatch):
    secret = "test-secret"
    client = _client_with_secret(monkeypatch, secret)
    token = _issue_token("user-abc", secret=secret, expires_in_seconds=300)

    me_response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    bootstrap_response = client.get("/v1/me/bootstrap", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 200
    assert me_response.json() == {
        "email": None,
        "home_city_id": None,
        "notifications_enabled": True,
        "notifications_paused_until": None,
    }
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["user_id"] == "user-abc"
