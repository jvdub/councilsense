from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.db import PILOT_CITY_ID


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


def _insert_meeting(
    client: TestClient,
    *,
    meeting_id: str,
    meeting_uid: str,
    title: str,
    created_at: str,
    city_id: str = PILOT_CITY_ID,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (meeting_id, city_id, meeting_uid, title, created_at, created_at),
    )


def _insert_city(client: TestClient, *, city_id: str, slug: str, name: str) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (city_id, slug, name, "UT", "America/Denver", 1, 2),
    )


def _set_home_city(client: TestClient, *, headers: dict[str, str], city_id: str = PILOT_CITY_ID) -> None:
    response = client.patch("/v1/me", headers=headers, json={"home_city_id": city_id})
    assert response.status_code == 200


def _insert_publication(
    client: TestClient,
    *,
    publication_id: str,
    meeting_id: str,
    publication_status: str,
    confidence_label: str,
    summary_text: str,
    key_decisions_json: str,
    key_actions_json: str,
    notable_topics_json: str,
    published_at: str,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO summary_publications (
            id,
            meeting_id,
            processing_run_id,
            publish_stage_outcome_id,
            version_no,
            publication_status,
            confidence_label,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json,
            published_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            publication_id,
            meeting_id,
            None,
            None,
            1,
            publication_status,
            confidence_label,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json,
            published_at,
            published_at,
        ),
    )


def _insert_claim(client: TestClient, *, claim_id: str, publication_id: str, claim_order: int, claim_text: str) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO publication_claims (id, publication_id, claim_order, claim_text)
        VALUES (?, ?, ?, ?)
        """,
        (claim_id, publication_id, claim_order, claim_text),
    )


def _insert_evidence_pointer(
    client: TestClient,
    *,
    pointer_id: str,
    claim_id: str,
    artifact_id: str,
    section_ref: str | None,
    char_start: int | None,
    char_end: int | None,
    excerpt: str,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO claim_evidence_pointers (
            id,
            claim_id,
            artifact_id,
            section_ref,
            char_start,
            char_end,
            excerpt
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (pointer_id, claim_id, artifact_id, section_ref, char_start, char_end, excerpt),
    )


def test_meeting_detail_returns_summary_sections_and_evidence_payload(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-detail", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-1",
        meeting_uid="uid-detail-1",
        title="Council Session",
        created_at="2026-02-20 12:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-detail-1",
        meeting_id="meeting-detail-1",
        publication_status="processed",
        confidence_label="high",
        summary_text="Council approved the annual safety plan.",
        key_decisions_json='["Approved annual safety plan"]',
        key_actions_json='["Staff to publish implementation memo"]',
        notable_topics_json='["Public safety","Budget"]',
        published_at="2026-02-20 13:00:00",
    )
    _insert_claim(
        client,
        claim_id="claim-detail-1",
        publication_id="pub-detail-1",
        claim_order=1,
        claim_text="The council approved the annual safety plan.",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-1",
        claim_id="claim-detail-1",
        artifact_id="artifact-minutes-1",
        section_ref="minutes.section.3",
        char_start=100,
        char_end=170,
        excerpt="Council voted 6-1 to approve the annual safety plan.",
    )

    response = client.get("/v1/meetings/meeting-detail-1", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "meeting-detail-1"
    assert payload["status"] == "processed"
    assert payload["confidence_label"] == "high"
    assert payload["summary"] == "Council approved the annual safety plan."
    assert payload["key_decisions"] == ["Approved annual safety plan"]
    assert payload["key_actions"] == ["Staff to publish implementation memo"]
    assert payload["notable_topics"] == ["Public safety", "Budget"]
    assert payload["claims"] == [
        {
            "id": "claim-detail-1",
            "claim_order": 1,
            "claim_text": "The council approved the annual safety plan.",
            "evidence": [
                {
                    "id": "ptr-detail-1",
                    "artifact_id": "artifact-minutes-1",
                    "section_ref": "minutes.section.3",
                    "char_start": 100,
                    "char_end": 170,
                    "excerpt": "Council voted 6-1 to approve the annual safety plan.",
                }
            ],
        }
    ]


def test_meeting_detail_includes_explicit_limited_confidence_label(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-limited", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-limited",
        meeting_uid="uid-detail-limited",
        title="Council Session Limited",
        created_at="2026-02-22 12:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-detail-limited",
        meeting_id="meeting-detail-limited",
        publication_status="limited_confidence",
        confidence_label="limited_confidence",
        summary_text="Limited-confidence summary pending stronger evidence.",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json='["Procurement"]',
        published_at="2026-02-22 13:00:00",
    )

    response = client.get("/v1/meetings/meeting-detail-limited", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "limited_confidence"
    assert payload["confidence_label"] == "limited_confidence"
    assert payload["notable_topics"] == ["Procurement"]
    assert payload["claims"] == []


def test_meeting_detail_returns_predictable_not_found_for_unknown_id(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="test-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-not-found", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    response = client.get(
        "/v1/meetings/missing-meeting-id",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Meeting not found",
            "details": {"meeting_id": "missing-meeting-id"},
        }
    }


def test_meeting_detail_denies_cross_city_lookup_without_city_leakage(monkeypatch) -> None:
    client = _client_with_configured_cities(
        monkeypatch,
        secret="test-secret",
        supported_city_ids=f"{PILOT_CITY_ID},other-city",
    )
    token = _issue_token("user-cross-city", secret="test-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers, city_id=PILOT_CITY_ID)

    _insert_city(client, city_id="other-city", slug="other-city-ut", name="Other City")
    _insert_meeting(
        client,
        meeting_id="meeting-foreign",
        meeting_uid="uid-foreign",
        title="Foreign City Session",
        created_at="2026-02-23 12:00:00",
        city_id="other-city",
    )

    response = client.get("/v1/meetings/meeting-foreign", headers=headers)

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Meeting not found",
            "details": {"meeting_id": "meeting-foreign"},
        }
    }
