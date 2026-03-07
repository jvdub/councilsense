from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from councilsense.api.routes.meetings import _merge_additive_blocks
from councilsense.app.main import create_app
from councilsense.app.settings import MeetingDetailAdditiveApiSettings
from councilsense.db import PILOT_CITY_ID


EVIDENCE_V2_KEYS = {
    "evidence_id",
    "document_id",
    "artifact_id",
    "document_kind",
    "section_path",
    "page_start",
    "page_end",
    "char_start",
    "char_end",
    "precision",
    "confidence",
    "excerpt",
}


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _st027_contract_fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st027_reader_api_additive_contract_examples.json"


def _load_st027_contract_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_st027_contract_fixture_path().read_text(encoding="utf-8")))


def _load_st027_contract_scenario(fixture_id: str) -> dict[str, Any]:
    scenarios = cast(list[dict[str, Any]], _load_st027_contract_bundle()["scenarios"])
    return next(scenario for scenario in scenarios if scenario["fixture_id"] == fixture_id)


def _with_reader_context(payload: dict[str, Any]) -> dict[str, Any]:
    created_at = str(payload.get("created_at") or "")
    meeting_date = created_at[:10] if len(created_at) >= 10 else None
    enriched = dict(payload)
    enriched.update(
        {
            "city_name": "Eagle Mountain",
            "meeting_date": meeting_date,
            "body_name": None,
            "source_document_kind": None,
            "source_document_url": None,
        }
    )
    return enriched


def _insert_meeting(
    client: TestClient,
    *,
    meeting_id: str,
    meeting_uid: str,
    title: str,
    created_at: str,
    updated_at: str | None = None,
    city_id: str = PILOT_CITY_ID,
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (meeting_id, city_id, meeting_uid, title, created_at, updated_at or created_at),
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
    publish_stage_outcome_id: str | None = None,
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
            publish_stage_outcome_id,
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
    document_id: str | None = None,
    span_id: str | None = None,
    document_kind: str | None = None,
    section_path: str | None = None,
    precision: str | None = None,
    confidence: str | None = None,
) -> None:
    app = cast(Any, client.app)
    if document_id is not None:
        resolved_document_kind = document_kind or "minutes"
        authority_level = "authoritative" if resolved_document_kind == "minutes" else "supplemental"
        meeting_id = cast(
            str,
            app.state.db_connection.execute(
                """
                SELECT sp.meeting_id
                FROM publication_claims pc
                INNER JOIN summary_publications sp ON sp.id = pc.publication_id
                WHERE pc.id = ?
                """,
                (claim_id,),
            ).fetchone()[0],
        )
        current_revision = cast(
            int,
            app.state.db_connection.execute(
                """
                SELECT COALESCE(MAX(revision_number), 0)
                FROM canonical_documents
                WHERE meeting_id = ? AND document_kind = ?
                """,
                (meeting_id, resolved_document_kind),
            ).fetchone()[0],
        )
        revision_number = current_revision + 1
        is_active_revision = 1 if current_revision == 0 else 0
        app.state.db_connection.execute(
            """
            INSERT OR IGNORE INTO canonical_documents (
                id,
                meeting_id,
                document_kind,
                revision_id,
                revision_number,
                is_active_revision,
                authority_level,
                authority_source,
                parser_name,
                parser_version,
                extraction_status,
                extraction_confidence,
                extracted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                meeting_id,
                resolved_document_kind,
                f"revision-{document_id}",
                revision_number,
                is_active_revision,
                authority_level,
                "test-fixture",
                "test-parser",
                "v1",
                "processed",
                0.95,
                "2026-03-01T00:00:00Z",
            ),
        )

    if span_id is not None and document_id is not None:
        app.state.db_connection.execute(
            """
            INSERT OR IGNORE INTO canonical_document_spans (
                id,
                canonical_document_id,
                artifact_id,
                artifact_scope,
                stable_section_path,
                start_char_offset,
                end_char_offset,
                locator_fingerprint,
                parser_name,
                parser_version,
                span_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span_id,
                document_id,
                artifact_id,
                "body",
                section_path or section_ref or "artifact",
                char_start,
                char_end,
                f"fingerprint-{span_id}",
                "test-parser",
                "v1",
                excerpt,
            ),
        )

    app.state.db_connection.execute(
        """
        INSERT INTO claim_evidence_pointers (
            id,
            claim_id,
            artifact_id,
            section_ref,
            char_start,
            char_end,
            excerpt,
            document_id,
            span_id,
            document_kind,
            section_path,
            precision,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pointer_id,
            claim_id,
            artifact_id,
            section_ref,
            char_start,
            char_end,
            excerpt,
            document_id,
            span_id,
            document_kind,
            section_path,
            precision,
            confidence,
        ),
    )


def _insert_ingest_stage_outcome(
    client: TestClient,
    *,
    outcome_id: str,
    run_id: str,
    city_id: str,
    meeting_id: str,
    candidate_url: str,
    selected_event_name: str = "City Council Meeting",
    selected_event_date: str = "2026-02-20",
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT OR IGNORE INTO processing_runs (
            id,
            city_id,
            cycle_id,
            status,
            parser_version,
            source_version,
            started_at
        )
        VALUES (?, ?, ?, 'processed', ?, ?, ?)
        """,
        (
            run_id,
            city_id,
            f"cycle-{run_id}",
            "v1",
            "test-source",
            "2026-02-20T12:00:00Z",
        ),
    )
    app.state.db_connection.execute(
        """
        INSERT INTO processing_stage_outcomes (
            id,
            run_id,
            city_id,
            meeting_id,
            stage_name,
            status,
            metadata_json,
            started_at,
            finished_at
        )
        VALUES (?, ?, ?, ?, 'ingest', 'processed', ?, ?, ?)
        """,
        (
            outcome_id,
            run_id,
            city_id,
            meeting_id,
            json.dumps(
                {
                    "candidate_url": candidate_url,
                    "selected_event_name": selected_event_name,
                    "selected_event_date": selected_event_date,
                },
                separators=(",", ":"),
            ),
            "2026-02-20T12:10:00Z",
            "2026-02-20T12:11:00Z",
        ),
    )


def _insert_publish_stage_outcome(
    client: TestClient,
    *,
    outcome_id: str,
    run_id: str,
    city_id: str,
    meeting_id: str,
    metadata: dict[str, Any],
) -> None:
    app = cast(Any, client.app)
    app.state.db_connection.execute(
        """
        INSERT OR IGNORE INTO processing_runs (
            id,
            city_id,
            cycle_id,
            status,
            parser_version,
            source_version,
            started_at
        )
        VALUES (?, ?, ?, 'processed', ?, ?, ?)
        """,
        (
            run_id,
            city_id,
            f"cycle-{run_id}",
            "v1",
            "test-source",
            "2026-03-07T09:00:00Z",
        ),
    )
    app.state.db_connection.execute(
        """
        INSERT INTO processing_stage_outcomes (
            id,
            run_id,
            city_id,
            meeting_id,
            stage_name,
            status,
            metadata_json,
            started_at,
            finished_at
        )
        VALUES (?, ?, ?, ?, 'publish', 'processed', ?, ?, ?)
        """,
        (
            outcome_id,
            run_id,
            city_id,
            meeting_id,
            json.dumps(metadata, separators=(",", ":"), sort_keys=True),
            "2026-03-07T09:05:00Z",
            "2026-03-07T09:06:00Z",
        ),
    )


def _seed_st027_contract_scenario(
    client: TestClient,
    *,
    scenario: dict[str, Any],
    additive_blocks_override: dict[str, Any] | None = None,
) -> None:
    payload = cast(dict[str, Any], scenario["payload"])
    meeting_id = cast(str, payload["id"])
    publication_id = cast(str, payload["publication_id"])

    _insert_meeting(
        client,
        meeting_id=meeting_id,
        meeting_uid=cast(str, payload["meeting_uid"]),
        title=cast(str, payload["title"]),
        created_at=cast(str, payload["created_at"]),
        updated_at=cast(str, payload["updated_at"]),
        city_id=cast(str, payload["city_id"]),
    )

    additive_blocks = additive_blocks_override
    if additive_blocks is None:
        additive_blocks = {
            block_name: payload[block_name]
            for block_name in ("planned", "outcomes", "planned_outcome_mismatches")
            if block_name in payload
        }

    publish_stage_outcome_id: str | None = None
    if additive_blocks:
        publish_stage_outcome_id = f"outcome-{publication_id}"
        _insert_publish_stage_outcome(
            client,
            outcome_id=publish_stage_outcome_id,
            run_id=f"run-{publication_id}",
            city_id=cast(str, payload["city_id"]),
            meeting_id=meeting_id,
            metadata={"additive_blocks": additive_blocks},
        )

    _insert_publication(
        client,
        publication_id=publication_id,
        meeting_id=meeting_id,
        publication_status=cast(str, payload["status"]),
        confidence_label=cast(str, payload["confidence_label"]),
        summary_text=cast(str | None, payload["summary"]) or "",
        key_decisions_json=json.dumps(payload["key_decisions"], separators=(",", ":")),
        key_actions_json=json.dumps(payload["key_actions"], separators=(",", ":")),
        notable_topics_json=json.dumps(payload["notable_topics"], separators=(",", ":")),
        published_at=cast(str, payload["published_at"]),
        publish_stage_outcome_id=publish_stage_outcome_id,
    )


def test_meeting_detail_additive_blocks_include_full_source_item_evidence_v2_when_flag_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")
    client = _client_with_configured_cities(monkeypatch, secret="additive-full-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-additive-full", secret="additive-full-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-additive-full",
        meeting_uid="uid-detail-additive-full",
        title="Additive Full Source Meeting",
        created_at="2026-03-07 09:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-publish-detail-additive-full",
        run_id="run-detail-additive-full",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-additive-full",
        metadata={
            "additive_blocks": {
                "planned": {
                    "generated_at": "2026-03-07T09:00:00Z",
                    "source_coverage": {"minutes": "present", "agenda": "present", "packet": "present"},
                    "items": [
                        {
                            "planned_id": "planned-1",
                            "title": "Procurement contract approval",
                            "category": "procurement",
                            "status": "planned",
                            "confidence": "high",
                            "evidence_references_v2": [
                                {
                                    "evidence_id": "plan-ev-1",
                                    "document_id": "doc-agenda-1",
                                    "document_kind": "agenda",
                                    "artifact_id": "artifact-agenda-1",
                                    "section_path": "agenda.items.8",
                                    "page_start": 5,
                                    "page_end": 5,
                                    "char_start": None,
                                    "char_end": None,
                                    "precision": "section",
                                    "confidence": "high",
                                    "excerpt": "Approve the procurement contract for fleet replacement.",
                                }
                            ],
                        }
                    ],
                },
                "outcomes": {
                    "generated_at": "2026-03-07T09:20:00Z",
                    "authority_source": "minutes",
                    "items": [
                        {
                            "outcome_id": "outcome-1",
                            "title": "Procurement contract deferred",
                            "result": "deferred",
                            "confidence": "high",
                            "evidence_references_v2": [
                                {
                                    "evidence_id": "outcome-ev-1",
                                    "document_id": "doc-minutes-1",
                                    "document_kind": "minutes",
                                    "artifact_id": "artifact-minutes-1",
                                    "section_path": "minutes.section.8.vote",
                                    "page_start": 7,
                                    "page_end": 7,
                                    "char_start": 141,
                                    "char_end": 224,
                                    "precision": "offset",
                                    "confidence": "high",
                                    "excerpt": "Council deferred the procurement contract pending revised terms.",
                                }
                            ],
                        }
                    ],
                },
                "planned_outcome_mismatches": {
                    "summary": {"total": 1, "high": 1, "medium": 0, "low": 0},
                    "items": [
                        {
                            "mismatch_id": "mismatch-1",
                            "planned_id": "planned-1",
                            "outcome_id": "outcome-1",
                            "severity": "high",
                            "mismatch_type": "disposition_change",
                            "description": "Agenda planned approval but recorded outcome is deferment.",
                            "reason_codes": ["outcome_changed"],
                            "evidence_references_v2": [
                                {
                                    "evidence_id": "mismatch-ev-1",
                                    "document_id": "doc-minutes-1",
                                    "document_kind": "minutes",
                                    "artifact_id": "artifact-minutes-1",
                                    "section_path": "minutes.section.8.vote",
                                    "page_start": 7,
                                    "page_end": 7,
                                    "char_start": 141,
                                    "char_end": 224,
                                    "precision": "offset",
                                    "confidence": "high",
                                    "excerpt": "Council deferred the procurement contract pending revised terms.",
                                }
                            ],
                        }
                    ],
                },
            }
        },
    )
    _insert_publication(
        client,
        publication_id="pub-detail-additive-full",
        meeting_id="meeting-detail-additive-full",
        publication_status="processed",
        confidence_label="high",
        summary_text="Council approved the consent agenda and deferred one procurement item.",
        key_decisions_json='["Approved consent agenda"]',
        key_actions_json='["Staff to revise the procurement contract"]',
        notable_topics_json='["Consent agenda","Procurement"]',
        published_at="2026-03-07T09:30:00Z",
        publish_stage_outcome_id="outcome-publish-detail-additive-full",
    )

    response = client.get("/v1/meetings/meeting-detail-additive-full", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned"]["items"][0]["evidence_references_v2"] == [
        {
            "evidence_id": "plan-ev-1",
            "document_id": "doc-agenda-1",
            "artifact_id": "artifact-agenda-1",
            "document_kind": "agenda",
            "section_path": "agenda.items.8",
            "page_start": 5,
            "page_end": 5,
            "char_start": None,
            "char_end": None,
            "precision": "section",
            "confidence": "high",
            "excerpt": "Approve the procurement contract for fleet replacement.",
        }
    ]
    assert payload["outcomes"]["items"][0]["evidence_references_v2"] == [
        {
            "evidence_id": "outcome-ev-1",
            "document_id": "doc-minutes-1",
            "artifact_id": "artifact-minutes-1",
            "document_kind": "minutes",
            "section_path": "minutes.section.8.vote",
            "page_start": 7,
            "page_end": 7,
            "char_start": 141,
            "char_end": 224,
            "precision": "offset",
            "confidence": "high",
            "excerpt": "Council deferred the procurement contract pending revised terms.",
        }
    ]
    assert payload["planned_outcome_mismatches"]["items"][0]["evidence_references_v2"] == [
        {
            "evidence_id": "mismatch-ev-1",
            "document_id": "doc-minutes-1",
            "artifact_id": "artifact-minutes-1",
            "document_kind": "minutes",
            "section_path": "minutes.section.8.vote",
            "page_start": 7,
            "page_end": 7,
            "char_start": 141,
            "char_end": 224,
            "precision": "offset",
            "confidence": "high",
            "excerpt": "Council deferred the procurement contract pending revised terms.",
        }
    ]


def test_meeting_detail_additive_blocks_omit_item_level_evidence_v2_when_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")
    client = _client_with_configured_cities(monkeypatch, secret="additive-partial-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-additive-partial", secret="additive-partial-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-additive-partial",
        meeting_uid="uid-detail-additive-partial",
        title="Additive Partial Source Meeting",
        created_at="2026-03-07 10:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-publish-detail-additive-partial",
        run_id="run-detail-additive-partial",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-additive-partial",
        metadata={
            "planned": {
                "generated_at": "2026-03-07T10:00:00Z",
                "source_coverage": {"minutes": "missing", "agenda": "present", "packet": "present"},
                "items": [
                    {
                        "planned_id": "planned-2",
                        "title": "Utility rate adjustment resolution",
                        "category": "ordinance",
                        "status": "planned",
                        "confidence": "medium",
                        "evidence_references_v2": None,
                    }
                ],
            },
            "outcomes": {
                "generated_at": "2026-03-07T10:10:00Z",
                "authority_source": "minutes",
                "items": [
                    {
                        "outcome_id": "outcome-2",
                        "title": "Outcome unavailable pending minutes",
                        "result": "unresolved",
                        "confidence": "low",
                    }
                ],
            },
            "planned_outcome_mismatches": {
                "summary": {"total": 1, "high": 0, "medium": 1, "low": 0},
                "items": [
                    {
                        "mismatch_id": "mismatch-2",
                        "planned_id": "planned-2",
                        "outcome_id": None,
                        "severity": "medium",
                        "mismatch_type": "authority_missing",
                        "description": "Minutes are unavailable, so the final outcome cannot yet be compared against the planned item.",
                        "reason_codes": ["missing_authoritative_minutes"],
                        "evidence_references_v2": None,
                    }
                ],
            },
        },
    )
    _insert_publication(
        client,
        publication_id="pub-detail-additive-partial",
        meeting_id="meeting-detail-additive-partial",
        publication_status="limited_confidence",
        confidence_label="limited_confidence",
        summary_text="Agenda and packet support planned work, but authoritative minutes are unavailable.",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json='["Utility rates"]',
        published_at="2026-03-07T10:10:00Z",
        publish_stage_outcome_id="outcome-publish-detail-additive-partial",
    )

    response = client.get("/v1/meetings/meeting-detail-additive-partial", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert "evidence_references_v2" not in payload["planned"]["items"][0]
    assert "evidence_references_v2" not in payload["outcomes"]["items"][0]
    assert "evidence_references_v2" not in payload["planned_outcome_mismatches"]["items"][0]


def test_meeting_detail_additive_blocks_preserve_empty_no_mismatch_block_when_flag_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")
    client = _client_with_configured_cities(monkeypatch, secret="additive-no-mismatch-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-additive-no-mismatch", secret="additive-no-mismatch-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-additive-no-mismatch",
        meeting_uid="uid-detail-additive-no-mismatch",
        title="Additive No Mismatch Meeting",
        created_at="2026-03-07 11:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-publish-detail-additive-no-mismatch",
        run_id="run-detail-additive-no-mismatch",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-additive-no-mismatch",
        metadata={
            "planned": {
                "generated_at": "2026-03-07T11:00:00Z",
                "source_coverage": {"minutes": "present", "agenda": "present", "packet": "missing"},
                "items": [{"planned_id": "planned-3", "title": "Consent agenda", "status": "planned", "confidence": "high"}],
            },
            "outcomes": {
                "generated_at": "2026-03-07T11:05:00Z",
                "authority_source": "minutes",
                "items": [{"outcome_id": "outcome-3", "title": "Consent agenda approved", "result": "approved", "confidence": "high"}],
            },
            "planned_outcome_mismatches": {
                "summary": {"total": 0, "high": 0, "medium": 0, "low": 0},
                "items": [],
            },
        },
    )
    _insert_publication(
        client,
        publication_id="pub-detail-additive-no-mismatch",
        meeting_id="meeting-detail-additive-no-mismatch",
        publication_status="processed",
        confidence_label="high",
        summary_text="Council approved the consent agenda.",
        key_decisions_json='["Approved consent agenda"]',
        key_actions_json="[]",
        notable_topics_json='["Consent agenda"]',
        published_at="2026-03-07T11:06:00Z",
        publish_stage_outcome_id="outcome-publish-detail-additive-no-mismatch",
    )

    response = client.get("/v1/meetings/meeting-detail-additive-no-mismatch", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_outcome_mismatches"] == {
        "summary": {"total": 0, "high": 0, "medium": 0, "low": 0},
        "items": [],
    }


def test_meeting_detail_flag_off_remains_baseline_equivalent_when_publish_metadata_has_additive_blocks(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="additive-flag-off-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-additive-flag-off", secret="additive-flag-off-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-additive-flag-off",
        meeting_uid="uid-detail-additive-flag-off",
        title="Additive Flag Off Meeting",
        created_at="2026-03-07 12:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-publish-detail-additive-flag-off",
        run_id="run-detail-additive-flag-off",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-additive-flag-off",
        metadata={
            "planned": {"generated_at": "2026-03-07T12:00:00Z", "items": [{"planned_id": "planned-4"}]},
            "outcomes": {"generated_at": "2026-03-07T12:05:00Z", "items": [{"outcome_id": "outcome-4"}]},
            "planned_outcome_mismatches": {"summary": {"total": 0, "high": 0, "medium": 0, "low": 0}, "items": []},
        },
    )
    _insert_publication(
        client,
        publication_id="pub-detail-additive-flag-off",
        meeting_id="meeting-detail-additive-flag-off",
        publication_status="processed",
        confidence_label="high",
        summary_text="Baseline meeting detail should not leak additive fields.",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-07T12:06:00Z",
        publish_stage_outcome_id="outcome-publish-detail-additive-flag-off",
    )

    response = client.get("/v1/meetings/meeting-detail-additive-flag-off", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "id",
        "city_id",
        "city_name",
        "meeting_uid",
        "title",
        "created_at",
        "updated_at",
        "meeting_date",
        "body_name",
        "source_document_kind",
        "source_document_url",
        "status",
        "confidence_label",
        "reader_low_confidence",
        "publication_id",
        "published_at",
        "summary",
        "key_decisions",
        "key_actions",
        "notable_topics",
        "evidence_references_v2",
        "evidence_references",
        "claims",
    }


@pytest.mark.parametrize(
    "fixture_id",
    [
        "st027-flag-on-evidence-v2-available",
        "st027-flag-on-evidence-v2-unavailable",
    ],
)
def test_st027_meeting_detail_matches_contract_fixture_when_additive_flag_enabled(monkeypatch, fixture_id: str) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")

    scenario = _load_st027_contract_scenario(fixture_id)
    payload = cast(dict[str, Any], scenario["payload"])
    client = _client_with_configured_cities(monkeypatch, secret=f"{fixture_id}-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token(f"user-{fixture_id}", secret=f"{fixture_id}-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _seed_st027_contract_scenario(client, scenario=scenario)

    response = client.get(f"/v1/meetings/{payload['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == _with_reader_context(payload)


def test_st027_flag_off_meeting_detail_matches_baseline_contract_fixture_even_with_hidden_additive_metadata(monkeypatch) -> None:
    baseline_scenario = _load_st027_contract_scenario("st027-flag-off-baseline")
    additive_scenario = _load_st027_contract_scenario("st027-flag-on-evidence-v2-available")
    baseline_payload = cast(dict[str, Any], baseline_scenario["payload"])
    additive_blocks = {
        block_name: cast(dict[str, Any], additive_scenario["payload"])[block_name]
        for block_name in ("planned", "outcomes", "planned_outcome_mismatches")
    }

    client = _client_with_configured_cities(monkeypatch, secret="st027-flag-off-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-st027-flag-off", secret="st027-flag-off-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _seed_st027_contract_scenario(
        client,
        scenario=baseline_scenario,
        additive_blocks_override=additive_blocks,
    )

    response = client.get(f"/v1/meetings/{baseline_payload['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == _with_reader_context(baseline_payload)


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
        document_id="canon-minutes-1",
        span_id="span-minutes-1",
        document_kind="minutes",
        section_path="minutes/section/3",
        precision="offset",
        confidence="high",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-2",
        claim_id="claim-detail-1",
        artifact_id="artifact-minutes-1",
        section_ref="minutes.section.3",
        char_start=100,
        char_end=170,
        excerpt="Council voted 6-1 to approve the annual safety plan.",
        document_id="canon-minutes-1",
        span_id="span-minutes-1-dup",
        document_kind="minutes",
        section_path="minutes/section/3",
        precision="offset",
        confidence="high",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-3",
        claim_id="claim-detail-1",
        artifact_id="artifact-minutes-2",
        section_ref="minutes.section.4",
        char_start=300,
        char_end=360,
        excerpt="Staff will publish the implementation memo by Friday.",
        document_id="canon-minutes-2",
        span_id="span-minutes-2",
        document_kind="minutes",
        section_path="minutes/section/4",
        precision="offset",
        confidence="medium",
    )
    _insert_ingest_stage_outcome(
        client,
        outcome_id="outcome-ingest-detail-1",
        run_id="run-detail-1",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-1",
        candidate_url="https://example.org/minutes/meeting-detail-1.pdf",
        selected_event_name="Eagle Mountain City Council",
        selected_event_date="2026-02-20",
    )

    response = client.get("/v1/meetings/meeting-detail-1", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "id",
        "city_id",
        "city_name",
        "meeting_uid",
        "title",
        "created_at",
        "updated_at",
        "meeting_date",
        "body_name",
        "source_document_kind",
        "source_document_url",
        "status",
        "confidence_label",
        "reader_low_confidence",
        "publication_id",
        "published_at",
        "summary",
        "key_decisions",
        "key_actions",
        "notable_topics",
        "evidence_references_v2",
        "evidence_references",
        "claims",
    }
    assert payload["id"] == "meeting-detail-1"
    assert payload["city_name"] == "Eagle Mountain"
    assert payload["meeting_date"] == "2026-02-20"
    assert payload["body_name"] == "Eagle Mountain City Council"
    assert payload["source_document_kind"] == "minutes"
    assert payload["source_document_url"] == "https://example.org/minutes/meeting-detail-1.pdf"
    assert payload["status"] == "processed"
    assert payload["confidence_label"] == "high"
    assert payload["reader_low_confidence"] is False
    assert payload["summary"] == "Council approved the annual safety plan."
    assert payload["key_decisions"] == ["Approved annual safety plan"]
    assert payload["key_actions"] == ["Staff to publish implementation memo"]
    assert payload["notable_topics"] == ["Public safety", "Budget"]
    assert payload["evidence_references_v2"] == [
        {
            "evidence_id": "ptr-detail-1",
            "document_id": "canon-minutes-1",
            "artifact_id": "artifact-minutes-1",
            "document_kind": "minutes",
            "section_path": "minutes/section/3",
            "page_start": None,
            "page_end": None,
            "char_start": 100,
            "char_end": 170,
            "precision": "offset",
            "confidence": "high",
            "excerpt": "Council voted 6-1 to approve the annual safety plan.",
        },
        {
            "evidence_id": "ptr-detail-3",
            "document_id": "canon-minutes-2",
            "artifact_id": "artifact-minutes-2",
            "document_kind": "minutes",
            "section_path": "minutes/section/4",
            "page_start": None,
            "page_end": None,
            "char_start": 300,
            "char_end": 360,
            "precision": "offset",
            "confidence": "medium",
            "excerpt": "Staff will publish the implementation memo by Friday.",
        },
    ]
    assert payload["evidence_references"] == [
        "Council voted 6-1 to approve the annual safety plan. | artifact-minutes-1#minutes.section.3:100-170",
        "Staff will publish the implementation memo by Friday. | artifact-minutes-2#minutes.section.4:300-360",
    ]
    assert payload["claims"] == [
        {
            "id": "claim-detail-1",
            "claim_order": 1,
            "claim_text": "The council approved the annual safety plan.",
            "evidence": [
                {
                    "id": "ptr-detail-1",
                    "artifact_id": "artifact-minutes-1",
                    "source_document_url": "https://example.org/minutes/meeting-detail-1.pdf",
                    "section_ref": "minutes.section.3",
                    "char_start": 100,
                    "char_end": 170,
                    "excerpt": "Council voted 6-1 to approve the annual safety plan.",
                },
                {
                    "id": "ptr-detail-2",
                    "artifact_id": "artifact-minutes-1",
                    "source_document_url": "https://example.org/minutes/meeting-detail-1.pdf",
                    "section_ref": "minutes.section.3",
                    "char_start": 100,
                    "char_end": 170,
                    "excerpt": "Council voted 6-1 to approve the annual safety plan.",
                },
                {
                    "id": "ptr-detail-3",
                    "artifact_id": "artifact-minutes-2",
                    "source_document_url": "https://example.org/minutes/meeting-detail-1.pdf",
                    "section_ref": "minutes.section.4",
                    "char_start": 300,
                    "char_end": 360,
                    "excerpt": "Staff will publish the implementation memo by Friday.",
                }
            ],
        }
    ]
    first_evidence = payload["claims"][0]["evidence"][0]
    assert set(first_evidence.keys()) == {
        "id",
        "artifact_id",
        "source_document_url",
        "section_ref",
        "char_start",
        "char_end",
        "excerpt",
    }


def test_meeting_detail_evidence_references_use_precision_ladder_and_stable_tie_breakers(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="meeting-detail-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-detail-precision", secret="meeting-detail-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-precision",
        meeting_uid="uid-detail-precision",
        title="Precision Ladder Meeting",
        created_at="2026-03-05 09:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-detail-precision",
        meeting_id="meeting-detail-precision",
        publication_status="processed",
        confidence_label="high",
        summary_text="Summary",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-05 10:00:00",
    )
    _insert_claim(
        client,
        claim_id="claim-detail-precision",
        publication_id="pub-detail-precision",
        claim_order=1,
        claim_text="Claim",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-file",
        claim_id="claim-detail-precision",
        artifact_id="artifact-zeta",
        section_ref="artifact.html",
        char_start=None,
        char_end=None,
        excerpt="File-level appendix note.",
        document_id="canon-packet-zeta",
        document_kind="packet",
        section_path="packet",
        precision="file",
        confidence="low",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-section",
        claim_id="claim-detail-precision",
        artifact_id="artifact-beta",
        section_ref="agenda.section.8",
        char_start=None,
        char_end=None,
        excerpt="Agenda section note.",
        document_id="canon-agenda-beta",
        document_kind="agenda",
        section_path="agenda/section/8",
        precision="section",
        confidence="medium",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-span-b",
        claim_id="claim-detail-precision",
        artifact_id="artifact-gamma",
        section_ref="minutes.section.7",
        char_start=None,
        char_end=None,
        excerpt="Later page reference.",
        document_id="canon-minutes-gamma",
        document_kind="minutes",
        section_path="minutes/page/7",
        precision="span",
        confidence="medium",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-offset",
        claim_id="claim-detail-precision",
        artifact_id="artifact-alpha",
        section_ref="minutes.section.2",
        char_start=10,
        char_end=42,
        excerpt="Precise minutes excerpt.",
        document_id="canon-minutes-alpha",
        span_id="span-minutes-alpha",
        document_kind="minutes",
        section_path="minutes/section/2",
        precision="offset",
        confidence="high",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-span-a",
        claim_id="claim-detail-precision",
        artifact_id="artifact-delta",
        section_ref="minutes.section.3",
        char_start=None,
        char_end=None,
        excerpt="Earlier page reference.",
        document_id="canon-minutes-delta",
        document_kind="minutes",
        section_path="minutes/page/3",
        precision="span",
        confidence="medium",
    )
    _insert_ingest_stage_outcome(
        client,
        outcome_id="outcome-ingest-detail-precision",
        run_id="run-detail-precision",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-precision",
        candidate_url="https://example.org/minutes/meeting-detail-precision.pdf",
    )

    first_response = client.get("/v1/meetings/meeting-detail-precision", headers=headers)
    second_response = client.get("/v1/meetings/meeting-detail-precision", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_payload = first_response.json()
    second_payload = second_response.json()

    assert first_payload["evidence_references"] == second_payload["evidence_references"]
    assert first_payload["evidence_references_v2"] == second_payload["evidence_references_v2"]
    assert first_payload["evidence_references"] == [
        "Precise minutes excerpt. | artifact-alpha#minutes.section.2:10-42",
        "Earlier page reference. | artifact-delta#minutes.section.3:?-?",
        "Later page reference. | artifact-gamma#minutes.section.7:?-?",
        "Agenda section note. | artifact-beta#agenda.section.8:?-?",
        "File-level appendix note. | artifact-zeta#artifact.html:?-?",
    ]
    assert first_payload["evidence_references_v2"] == [
        {
            "evidence_id": "ptr-detail-offset",
            "document_id": "canon-minutes-alpha",
            "artifact_id": "artifact-alpha",
            "document_kind": "minutes",
            "section_path": "minutes/section/2",
            "page_start": None,
            "page_end": None,
            "char_start": 10,
            "char_end": 42,
            "precision": "offset",
            "confidence": "high",
            "excerpt": "Precise minutes excerpt.",
        },
        {
            "evidence_id": "ptr-detail-span-a",
            "document_id": "canon-minutes-delta",
            "artifact_id": "artifact-delta",
            "document_kind": "minutes",
            "section_path": "minutes/page/3",
            "page_start": None,
            "page_end": None,
            "char_start": None,
            "char_end": None,
            "precision": "span",
            "confidence": "medium",
            "excerpt": "Earlier page reference.",
        },
        {
            "evidence_id": "ptr-detail-span-b",
            "document_id": "canon-minutes-gamma",
            "artifact_id": "artifact-gamma",
            "document_kind": "minutes",
            "section_path": "minutes/page/7",
            "page_start": None,
            "page_end": None,
            "char_start": None,
            "char_end": None,
            "precision": "span",
            "confidence": "medium",
            "excerpt": "Later page reference.",
        },
        {
            "evidence_id": "ptr-detail-section",
            "document_id": "canon-agenda-beta",
            "artifact_id": "artifact-beta",
            "document_kind": "agenda",
            "section_path": "agenda/section/8",
            "page_start": None,
            "page_end": None,
            "char_start": None,
            "char_end": None,
            "precision": "section",
            "confidence": "medium",
            "excerpt": "Agenda section note.",
        },
        {
            "evidence_id": "ptr-detail-file",
            "document_id": "canon-packet-zeta",
            "artifact_id": "artifact-zeta",
            "document_kind": "packet",
            "section_path": "packet",
            "page_start": None,
            "page_end": None,
            "char_start": None,
            "char_end": None,
            "precision": "file",
            "confidence": "low",
            "excerpt": "File-level appendix note.",
        },
    ]
    assert all(set(item.keys()) == EVIDENCE_V2_KEYS for item in first_payload["evidence_references_v2"])
    first_evidence = first_response.json()["claims"][0]["evidence"][0]
    assert set(first_evidence.keys()) == {
        "id",
        "artifact_id",
        "source_document_url",
        "section_ref",
        "char_start",
        "char_end",
        "excerpt",
    }


def test_meeting_detail_evidence_references_v2_supports_partial_metadata(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="partial-v2-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-detail-partial-v2", secret="partial-v2-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-partial-v2",
        meeting_uid="uid-detail-partial-v2",
        title="Partial V2 Meeting",
        created_at="2026-03-06 09:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-detail-partial-v2",
        meeting_id="meeting-detail-partial-v2",
        publication_status="processed",
        confidence_label="high",
        summary_text="Summary",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-06 10:00:00",
    )
    _insert_claim(
        client,
        claim_id="claim-detail-partial-v2",
        publication_id="pub-detail-partial-v2",
        claim_order=1,
        claim_text="Claim",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-partial-v2",
        claim_id="claim-detail-partial-v2",
        artifact_id="artifact-partial",
        section_ref="agenda.section.5",
        char_start=None,
        char_end=None,
        excerpt="Agenda preview supports the topic.",
        document_kind="agenda",
        section_path="agenda/section/5",
        precision="section",
    )

    response = client.get("/v1/meetings/meeting-detail-partial-v2", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_references_v2"] == [
        {
            "evidence_id": "ptr-detail-partial-v2",
            "document_id": None,
            "artifact_id": "artifact-partial",
            "document_kind": "agenda",
            "section_path": "agenda/section/5",
            "page_start": None,
            "page_end": None,
            "char_start": None,
            "char_end": None,
            "precision": "section",
            "confidence": None,
            "excerpt": "Agenda preview supports the topic.",
        }
    ]
    assert payload["evidence_references"] == [
        "Agenda preview supports the topic. | artifact-partial#agenda.section.5:?-?"
    ]


def test_meeting_detail_evidence_references_v2_is_empty_for_legacy_only_pointers(monkeypatch) -> None:
    client = _client_with_configured_cities(monkeypatch, secret="legacy-v2-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-detail-legacy-v2", secret="legacy-v2-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-legacy-v2",
        meeting_uid="uid-detail-legacy-v2",
        title="Legacy Evidence Meeting",
        created_at="2026-03-06 11:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-detail-legacy-v2",
        meeting_id="meeting-detail-legacy-v2",
        publication_status="processed",
        confidence_label="high",
        summary_text="Summary",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-06 12:00:00",
    )
    _insert_claim(
        client,
        claim_id="claim-detail-legacy-v2",
        publication_id="pub-detail-legacy-v2",
        claim_order=1,
        claim_text="Claim",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-legacy-v2",
        claim_id="claim-detail-legacy-v2",
        artifact_id="artifact-legacy",
        section_ref="minutes.section.9",
        char_start=20,
        char_end=60,
        excerpt="Legacy pointer without v2 metadata.",
    )

    response = client.get("/v1/meetings/meeting-detail-legacy-v2", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_references_v2"] == []
    assert payload["evidence_references"] == [
        "Legacy pointer without v2 metadata. | artifact-legacy#minutes.section.9:20-60"
    ]


def test_meeting_detail_legacy_evidence_compatibility_mapping_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MEETING_DETAIL_LEGACY_EVIDENCE_REFERENCES_ENABLED", "false")
    client = _client_with_configured_cities(monkeypatch, secret="compat-off-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-detail-compat-off", secret="compat-off-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-compat-off",
        meeting_uid="uid-detail-compat-off",
        title="Compatibility Off Meeting",
        created_at="2026-03-06 13:00:00",
    )
    _insert_publication(
        client,
        publication_id="pub-detail-compat-off",
        meeting_id="meeting-detail-compat-off",
        publication_status="processed",
        confidence_label="high",
        summary_text="Summary",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-06 14:00:00",
    )
    _insert_claim(
        client,
        claim_id="claim-detail-compat-off",
        publication_id="pub-detail-compat-off",
        claim_order=1,
        claim_text="Claim",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="ptr-detail-compat-off",
        claim_id="claim-detail-compat-off",
        artifact_id="artifact-compat-off",
        section_ref="minutes.section.1",
        char_start=1,
        char_end=20,
        excerpt="Canonical v2 evidence remains available.",
        document_id="canon-minutes-compat-off",
        span_id="span-minutes-compat-off",
        document_kind="minutes",
        section_path="minutes/section/1",
        precision="offset",
        confidence="high",
    )

    first_response = client.get("/v1/meetings/meeting-detail-compat-off", headers=headers)
    second_response = client.get("/v1/meetings/meeting-detail-compat-off", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_payload = first_response.json()
    second_payload = second_response.json()

    assert first_payload["status"] == "processed"
    assert first_payload["evidence_references_v2"] == second_payload["evidence_references_v2"] == [
        {
            "evidence_id": "ptr-detail-compat-off",
            "document_id": "canon-minutes-compat-off",
            "artifact_id": "artifact-compat-off",
            "document_kind": "minutes",
            "section_path": "minutes/section/1",
            "page_start": None,
            "page_end": None,
            "char_start": 1,
            "char_end": 20,
            "precision": "offset",
            "confidence": "high",
            "excerpt": "Canonical v2 evidence remains available.",
        }
    ]
    assert all(set(item.keys()) == EVIDENCE_V2_KEYS for item in first_payload["evidence_references_v2"])
    assert first_payload["evidence_references"] == second_payload["evidence_references"] == []


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
    assert payload["reader_low_confidence"] is True
    assert payload["notable_topics"] == ["Procurement"]
    assert payload["evidence_references"] == []
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


def test_meeting_detail_parity_guard_blocks_additive_payload_when_flag_off() -> None:
    with pytest.raises(ValueError, match="ST022 additive reader parity guard blocked additive leakage"):
        _merge_additive_blocks(
            payload={"id": "meeting-detail-guard"},
            detail=SimpleNamespace(planned={"items": []}),
            additive_api_settings=MeetingDetailAdditiveApiSettings(enabled=False, enabled_blocks=()),
        )


def test_meeting_detail_parity_guard_allows_explicitly_enabled_additive_blocks() -> None:
    payload = _merge_additive_blocks(
        payload={"id": "meeting-detail-guard"},
        detail=SimpleNamespace(additive_blocks={"planned": {"items": []}, "outcomes": {"items": []}}),
        additive_api_settings=MeetingDetailAdditiveApiSettings(
            enabled=True,
            enabled_blocks=("planned", "outcomes"),
        ),
    )

    assert payload == {
        "id": "meeting-detail-guard",
        "planned": {"items": []},
        "outcomes": {"items": []},
    }


def test_meeting_detail_parity_guard_rejects_disallowed_additive_blocks_when_flag_on() -> None:
    with pytest.raises(ValueError, match="offending_blocks=planned_outcome_mismatches"):
        _merge_additive_blocks(
            payload={"id": "meeting-detail-guard"},
            detail=SimpleNamespace(additive_blocks={"planned_outcome_mismatches": {"items": []}}),
            additive_api_settings=MeetingDetailAdditiveApiSettings(
                enabled=True,
                enabled_blocks=("planned", "outcomes"),
            ),
        )
