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


def _issue_token(user_id: str, *, secret: str, expires_in_seconds: int, email: str | None = None) -> str:
    header = _b64url({"alg": "HS256", "typ": "JWT"})
    exp = int((datetime.now(tz=UTC) + timedelta(seconds=expires_in_seconds)).timestamp())
    payload_data: dict[str, str | int] = {"sub": user_id, "exp": exp}
    if email is not None:
        payload_data["email"] = email
    payload = _b64url(payload_data)
    signing_input = f"{header}.{payload}"
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
    return f"{signing_input}.{signature}"


def _client_with_configured_cities(monkeypatch, *, secret: str, supported_city_ids: str) -> TestClient:
    monkeypatch.setenv("AUTH_SESSION_SECRET", secret)
    monkeypatch.setenv("SUPPORTED_CITY_IDS", supported_city_ids)
    return TestClient(create_app())


def test_get_me_returns_profile_state_with_email(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-a", secret="test-secret", expires_in_seconds=300, email="user-a@example.com")

    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "email": "user-a@example.com",
        "home_city_id": None,
        "notifications_enabled": True,
        "notifications_paused_until": None,
    }


def test_patch_me_updates_allowed_fields_for_authenticated_user_only(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token_user_a = _issue_token("user-a", secret="test-secret", expires_in_seconds=300)
    token_user_b = _issue_token("user-b", secret="test-secret", expires_in_seconds=300)
    headers_a = {"Authorization": f"Bearer {token_user_a}"}
    headers_b = {"Authorization": f"Bearer {token_user_b}"}

    patch_response = client.patch(
        "/v1/me",
        headers=headers_a,
        json={
            "home_city_id": "portland-or",
            "notifications_enabled": False,
            "notifications_paused_until": "2026-03-01T18:00:00Z",
        },
    )
    me_a_response = client.get("/v1/me", headers=headers_a)
    me_b_response = client.get("/v1/me", headers=headers_b)

    assert patch_response.status_code == 200
    assert patch_response.json() == {
        "email": None,
        "home_city_id": "portland-or",
        "notifications_enabled": False,
        "notifications_paused_until": "2026-03-01T18:00:00Z",
    }
    assert me_a_response.status_code == 200
    assert me_a_response.json() == patch_response.json()
    assert me_b_response.status_code == 200
    assert me_b_response.json() == {
        "email": None,
        "home_city_id": None,
        "notifications_enabled": True,
        "notifications_paused_until": None,
    }


def test_patch_me_accepts_partial_updates(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-partial", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.patch("/v1/me", headers=headers, json={"home_city_id": "seattle-wa"})
    partial = client.patch("/v1/me", headers=headers, json={"notifications_enabled": False})

    assert initial.status_code == 200
    assert partial.status_code == 200
    assert partial.json() == {
        "email": None,
        "home_city_id": "seattle-wa",
        "notifications_enabled": False,
        "notifications_paused_until": None,
    }


def test_patch_me_rejects_unsupported_city_id(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-invalid-city", secret="test-secret", expires_in_seconds=300)

    response = client.patch(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"home_city_id": "unknown-city"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Unsupported home_city_id",
            "details": {"home_city_id": "unknown-city"},
        }
    }


def test_patch_me_rejects_invalid_payload_shape(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-invalid-shape", secret="test-secret", expires_in_seconds=300)

    response = client.patch(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"notifications_paused_until": {"at": "2026-03-01T18:00:00Z"}},
    )

    assert response.status_code == 422


def test_patch_me_rejects_unknown_fields(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-extra-field", secret="test-secret", expires_in_seconds=300)

    response = client.patch(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"unknown": True},
    )

    assert response.status_code == 422
