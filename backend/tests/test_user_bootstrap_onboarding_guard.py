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


def _client_with_configured_cities(monkeypatch, *, secret: str, supported_city_ids: str) -> TestClient:
    monkeypatch.setenv("AUTH_SESSION_SECRET", secret)
    monkeypatch.setenv("SUPPORTED_CITY_IDS", supported_city_ids)
    return TestClient(create_app())


def test_bootstrap_marks_first_run_user_as_onboarding_required(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-new", secret="test-secret", expires_in_seconds=300)

    response = client.get("/v1/me/bootstrap", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-new",
        "home_city_id": None,
        "onboarding_required": True,
        "supported_city_ids": ["seattle-wa", "portland-or"],
    }


def test_bootstrap_marks_returning_user_as_onboarding_complete_after_valid_city_selection(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-returning", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}

    selection_response = client.patch("/v1/me/bootstrap", headers=headers, json={"home_city_id": "seattle-wa"})
    bootstrap_response = client.get("/v1/me/bootstrap", headers=headers)

    assert selection_response.status_code == 200
    assert selection_response.json() == {
        "user_id": "user-returning",
        "home_city_id": "seattle-wa",
        "onboarding_required": False,
        "supported_city_ids": ["seattle-wa", "portland-or"],
    }
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json() == selection_response.json()


def test_bootstrap_rejects_unsupported_city_id(monkeypatch):
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids="seattle-wa,portland-or",
    )
    token = _issue_token("user-invalid-city", secret="test-secret", expires_in_seconds=300)

    response = client.patch(
        "/v1/me/bootstrap",
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
