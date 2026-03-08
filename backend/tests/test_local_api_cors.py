from __future__ import annotations

from fastapi.testclient import TestClient

from councilsense.app.main import create_app


def _local_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("COUNCILSENSE_RUNTIME_ENV", "local")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "test-secret")
    return TestClient(create_app())


def test_local_cors_allows_host_ip_frontend_origins(monkeypatch) -> None:
    client = _local_client(monkeypatch)

    response = client.options(
        "/v1/me/bootstrap",
        headers={
            "Origin": "http://172.17.71.63:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://172.17.71.63:3000"


def test_local_cors_rejects_non_local_origins(monkeypatch) -> None:
    client = _local_client(monkeypatch)

    response = client.options(
        "/v1/me/bootstrap",
        headers={
            "Origin": "http://example.com:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers