from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.db import PILOT_CITY_ID


LEGACY_MEETING_DETAIL_FIELDS = {
    "id",
    "city_id",
    "meeting_uid",
    "title",
    "created_at",
    "updated_at",
    "status",
    "confidence_label",
    "reader_low_confidence",
    "publication_id",
    "published_at",
    "summary",
    "key_decisions",
    "key_actions",
    "notable_topics",
    "claims",
}
ALLOWED_ADDITIVE_FIELDS = {"evidence_references"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st018_evidence_references_contract_fixtures.json"


def _b64url(data: dict[str, Any]) -> str:
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


def _client(*, secret: str) -> tuple[TestClient, str | None, str | None]:
    original_secret = os.environ.get("AUTH_SESSION_SECRET")
    original_supported = os.environ.get("SUPPORTED_CITY_IDS")
    os.environ["AUTH_SESSION_SECRET"] = secret
    os.environ["SUPPORTED_CITY_IDS"] = PILOT_CITY_ID
    return TestClient(create_app()), original_secret, original_supported


def _cleanup_environment(*, original_secret: str | None, original_supported: str | None) -> None:
    if original_secret is None:
        os.environ.pop("AUTH_SESSION_SECRET", None)
    else:
        os.environ["AUTH_SESSION_SECRET"] = original_secret

    if original_supported is None:
        os.environ.pop("SUPPORTED_CITY_IDS", None)
    else:
        os.environ["SUPPORTED_CITY_IDS"] = original_supported


def _load_fixtures() -> list[dict[str, Any]]:
    payload = json.loads(_fixture_path().read_text(encoding="utf-8"))
    return cast(list[dict[str, Any]], payload["fixtures"])


def _set_home_city(client: TestClient, *, headers: dict[str, str]) -> None:
    response = client.patch("/v1/me", headers=headers, json={"home_city_id": PILOT_CITY_ID})
    assert response.status_code == 200


def _insert_fixture(client: TestClient, *, fixture: dict[str, Any]) -> None:
    app = cast(Any, client.app)
    meeting = cast(dict[str, Any], fixture["meeting"])
    publication = cast(dict[str, Any], fixture["publication"])

    app.state.db_connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            meeting["id"],
            PILOT_CITY_ID,
            meeting["uid"],
            meeting["title"],
            meeting["created_at"],
            meeting["created_at"],
        ),
    )
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
            publication["id"],
            meeting["id"],
            None,
            None,
            1,
            publication["status"],
            publication["confidence_label"],
            publication["summary"],
            json.dumps(publication["key_decisions"], separators=(",", ":")),
            json.dumps(publication["key_actions"], separators=(",", ":")),
            json.dumps(publication["notable_topics"], separators=(",", ":")),
            publication["published_at"],
            publication["published_at"],
        ),
    )

    for claim in cast(list[dict[str, Any]], fixture["claims"]):
        app.state.db_connection.execute(
            """
            INSERT INTO publication_claims (id, publication_id, claim_order, claim_text)
            VALUES (?, ?, ?, ?)
            """,
            (claim["id"], publication["id"], claim["claim_order"], claim["claim_text"]),
        )
        for evidence in cast(list[dict[str, Any]], claim["evidence"]):
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
                (
                    evidence["id"],
                    claim["id"],
                    evidence["artifact_id"],
                    evidence.get("section_ref"),
                    evidence.get("char_start"),
                    evidence.get("char_end"),
                    evidence["excerpt"],
                ),
            )


def test_st018_fixture_contract_for_evidence_present_and_sparse_behaviors() -> None:
    fixtures = _load_fixtures()

    for fixture in fixtures:
        client, original_secret, original_supported = _client(secret="st018-contract-secret")
        try:
            token = _issue_token(f"user-{fixture['fixture_id']}", secret="st018-contract-secret", expires_in_seconds=300)
            headers = {"Authorization": f"Bearer {token}"}
            _set_home_city(client, headers=headers)
            _insert_fixture(client, fixture=fixture)

            meeting_id = cast(dict[str, Any], fixture["meeting"])["id"]
            response = client.get(f"/v1/meetings/{meeting_id}", headers=headers)
            assert response.status_code == 200, (
                f"fixture={fixture['fixture_id']} expected status=200 got {response.status_code}"
            )
            payload = response.json()
            expected_references = fixture["expected_evidence_references"]

            assert payload["evidence_references"] == expected_references, (
                "fixture="
                f"{fixture['fixture_id']} field_path=$.evidence_references "
                f"expected={expected_references} actual={payload['evidence_references']}"
            )

            second_response = client.get(f"/v1/meetings/{meeting_id}", headers=headers)
            assert second_response.status_code == 200
            second_payload = second_response.json()
            assert second_payload["evidence_references"] == payload["evidence_references"], (
                f"fixture={fixture['fixture_id']} field_path=$.evidence_references "
                "expected deterministic serialization across reruns"
            )

            if fixture["evidence_mode"] == "present":
                assert payload["evidence_references"], (
                    f"fixture={fixture['fixture_id']} field_path=$.evidence_references expected non-empty list"
                )
            else:
                assert payload["evidence_references"] == [], (
                    f"fixture={fixture['fixture_id']} field_path=$.evidence_references expected explicit empty list"
                )
        finally:
            client.close()
            _cleanup_environment(original_secret=original_secret, original_supported=original_supported)


def test_st018_gate_a_legacy_fields_remain_compatible_with_only_additive_delta() -> None:
    fixture = _load_fixtures()[0]
    client, original_secret, original_supported = _client(secret="st018-gate-a-secret")
    try:
        token = _issue_token("user-st018-gate-a", secret="st018-gate-a-secret", expires_in_seconds=300)
        headers = {"Authorization": f"Bearer {token}"}
        _set_home_city(client, headers=headers)
        _insert_fixture(client, fixture=fixture)

        meeting_id = cast(dict[str, Any], fixture["meeting"])["id"]
        response = client.get(f"/v1/meetings/{meeting_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()

        current_fields = set(payload.keys())
        missing_legacy = LEGACY_MEETING_DETAIL_FIELDS - current_fields
        additive_delta = current_fields - LEGACY_MEETING_DETAIL_FIELDS

        assert not missing_legacy, (
            "field_path=$ missing legacy fields "
            f"{sorted(missing_legacy)}"
        )
        assert additive_delta == ALLOWED_ADDITIVE_FIELDS, (
            "field_path=$ additive delta mismatch "
            f"expected={sorted(ALLOWED_ADDITIVE_FIELDS)} actual={sorted(additive_delta)}"
        )

        assert payload["id"] == cast(dict[str, Any], fixture["meeting"])["id"]
        assert payload["summary"] == cast(dict[str, Any], fixture["publication"])["summary"]
        assert payload["key_decisions"] == cast(dict[str, Any], fixture["publication"])["key_decisions"]
        assert payload["key_actions"] == cast(dict[str, Any], fixture["publication"])["key_actions"]
        assert payload["notable_topics"] == cast(dict[str, Any], fixture["publication"])["notable_topics"]
    finally:
        client.close()
        _cleanup_environment(original_secret=original_secret, original_supported=original_supported)
