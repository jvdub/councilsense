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

from councilsense.api.routes.meetings import _build_follow_up_prompt_suggestions
from councilsense.api.routes.meetings import _merge_additive_blocks
from councilsense.api.routes.meetings import _merge_follow_up_prompt_suggestions
from councilsense.api.routes.meetings import _merge_resident_relevance_fields
from councilsense.app.main import create_app
from councilsense.app.settings import MeetingDetailAdditiveApiSettings
from councilsense.app.settings import MeetingDetailFollowUpPromptsApiSettings
from councilsense.app.settings import MeetingDetailResidentRelevanceApiSettings
from councilsense.db import PILOT_CITY_ID
from councilsense.db.meetings import MeetingDetail
from councilsense.db.meetings import MeetingDetailClaim
from councilsense.db.meetings import MeetingDetailEvidencePointer


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


def _st033_contract_fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st033_resident_relevance_additive_contract_examples.json"


def _st035_contract_fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st035_follow_up_prompts_additive_contract_examples.json"


def _load_st027_contract_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_st027_contract_fixture_path().read_text(encoding="utf-8")))


def _load_st033_contract_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_st033_contract_fixture_path().read_text(encoding="utf-8")))


def _load_st035_contract_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_st035_contract_fixture_path().read_text(encoding="utf-8")))


def _load_st027_contract_scenario(fixture_id: str) -> dict[str, Any]:
    scenarios = cast(list[dict[str, Any]], _load_st027_contract_bundle()["scenarios"])
    return next(scenario for scenario in scenarios if scenario["fixture_id"] == fixture_id)


def _load_st033_contract_scenario(fixture_id: str) -> dict[str, Any]:
    scenarios = cast(list[dict[str, Any]], _load_st033_contract_bundle()["scenarios"])
    return next(scenario for scenario in scenarios if scenario["fixture_id"] == fixture_id)


def _load_st035_contract_scenario(fixture_id: str) -> dict[str, Any]:
    scenarios = cast(list[dict[str, Any]], _load_st035_contract_bundle()["scenarios"])
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
            "source_document_kind": payload.get("source_document_kind"),
            "source_document_url": payload.get("source_document_url"),
        }
    )
    return enriched


def _strip_st033_resident_relevance_fields(value: object) -> object:
    if isinstance(value, list):
        return [_strip_st033_resident_relevance_fields(item) for item in value]

    if not isinstance(value, dict):
        return value

    return {
        key: _strip_st033_resident_relevance_fields(item)
        for key, item in value.items()
        if key not in {"structured_relevance", "subject", "location", "action", "scale", "impact_tags"}
    }


def _strip_st035_follow_up_prompt_fields(value: object) -> object:
    if isinstance(value, list):
        return [_strip_st035_follow_up_prompt_fields(item) for item in value]

    if not isinstance(value, dict):
        return value

    return {
        key: _strip_st035_follow_up_prompt_fields(item)
        for key, item in value.items()
        if key != "suggested_prompts"
    }


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


def _scramble_resident_relevance_fields(value: dict[str, Any]) -> dict[str, Any]:
    scrambled = cast(dict[str, Any], json.loads(json.dumps(value)))

    for field_name in ("subject", "location", "action", "scale"):
        field = scrambled.get(field_name)
        if isinstance(field, dict) and isinstance(field.get("evidence_references_v2"), list):
            field["evidence_references_v2"] = list(reversed(cast(list[dict[str, Any]], field["evidence_references_v2"])))

    impact_tags = scrambled.get("impact_tags")
    if isinstance(impact_tags, list):
        for tag in impact_tags:
            if isinstance(tag, dict) and isinstance(tag.get("evidence_references_v2"), list):
                tag["evidence_references_v2"] = list(reversed(cast(list[dict[str, Any]], tag["evidence_references_v2"])))
        scrambled["impact_tags"] = list(reversed(impact_tags))

    return scrambled


def _scramble_resident_relevance_block(value: dict[str, Any]) -> dict[str, Any]:
    scrambled = cast(dict[str, Any], json.loads(json.dumps(value)))
    items = scrambled.get("items")
    if isinstance(items, list):
        scrambled["items"] = [
            _scramble_resident_relevance_fields(item) if isinstance(item, dict) else item
            for item in items
        ]
    return scrambled


def _seed_st033_contract_scenario(
    client: TestClient,
    *,
    scenario: dict[str, Any],
    scramble_projection_ordering: bool,
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

    metadata: dict[str, Any] = {}
    structured_relevance = payload.get("structured_relevance")
    if isinstance(structured_relevance, dict):
        metadata["structured_relevance"] = (
            _scramble_resident_relevance_fields(structured_relevance)
            if scramble_projection_ordering
            else cast(dict[str, Any], json.loads(json.dumps(structured_relevance)))
        )

    additive_blocks: dict[str, Any] = {}
    for block_name in ("planned", "outcomes", "planned_outcome_mismatches"):
        block = payload.get(block_name)
        if not isinstance(block, dict):
            continue
        additive_blocks[block_name] = (
            _scramble_resident_relevance_block(block)
            if scramble_projection_ordering and block_name in {"planned", "outcomes"}
            else cast(dict[str, Any], json.loads(json.dumps(block)))
        )

    if additive_blocks:
        metadata["additive_blocks"] = additive_blocks

    publish_stage_outcome_id = f"outcome-{publication_id}"
    _insert_publish_stage_outcome(
        client,
        outcome_id=publish_stage_outcome_id,
        run_id=f"run-{publication_id}",
        city_id=cast(str, payload["city_id"]),
        meeting_id=meeting_id,
        metadata=metadata,
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


def _seed_st035_contract_scenario(client: TestClient, *, scenario: dict[str, Any]) -> None:
    payload = cast(dict[str, Any], scenario["payload"])
    publish_metadata = cast(dict[str, Any], scenario.get("publish_metadata") or {})
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

    publish_stage_outcome_id = f"outcome-{publication_id}"
    _insert_publish_stage_outcome(
        client,
        outcome_id=publish_stage_outcome_id,
        run_id=f"run-{publication_id}",
        city_id=cast(str, payload["city_id"]),
        meeting_id=meeting_id,
        metadata=publish_metadata,
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

    for claim in cast(list[dict[str, Any]], payload.get("claims") or []):
        claim_id = cast(str, claim["id"])
        _insert_claim(
            client,
            claim_id=claim_id,
            publication_id=publication_id,
            claim_order=cast(int, claim["claim_order"]),
            claim_text=cast(str, claim["claim_text"]),
        )
        for evidence in cast(list[dict[str, Any]], claim.get("evidence") or []):
            matching_reference = next(
                (
                    reference
                    for reference in cast(list[dict[str, Any]], payload.get("evidence_references_v2") or [])
                    if reference.get("evidence_id") == evidence.get("id")
                ),
                None,
            )
            _insert_evidence_pointer(
                client,
                pointer_id=cast(str, evidence["id"]),
                claim_id=claim_id,
                artifact_id=cast(str, evidence["artifact_id"]),
                section_ref=cast(str | None, evidence.get("section_ref")),
                char_start=cast(int | None, evidence.get("char_start")),
                char_end=cast(int | None, evidence.get("char_end")),
                excerpt=cast(str, evidence["excerpt"]),
                document_id=cast(str | None, None if matching_reference is None else matching_reference.get("document_id")),
                span_id=(None if matching_reference is None else f"span-{matching_reference['evidence_id']}"),
                document_kind=cast(str | None, None if matching_reference is None else matching_reference.get("document_kind")),
                section_path=cast(str | None, None if matching_reference is None else matching_reference.get("section_path")),
                precision=cast(str | None, None if matching_reference is None else matching_reference.get("precision")),
                confidence=cast(str | None, None if matching_reference is None else matching_reference.get("confidence")),
            )


def _meeting_detail_with_follow_up_prompt_inputs(
    *,
    structured_relevance: dict[str, Any] | None,
    key_actions: tuple[str, ...],
    claims: tuple[MeetingDetailClaim, ...],
) -> MeetingDetail:
    return MeetingDetail(
        id="meeting-follow-up-test",
        city_id=PILOT_CITY_ID,
        city_name="Eagle Mountain",
        meeting_uid="uid-follow-up-test",
        title="Follow Up Prompt Test Meeting",
        created_at="2026-03-09T12:00:00Z",
        updated_at="2026-03-09T12:05:00Z",
        meeting_date="2026-03-09",
        body_name=None,
        source_document_kind="minutes",
        source_document_url="https://example.org/minutes/follow-up-test.pdf",
        publication_id="pub-follow-up-test",
        publication_status="processed",
        confidence_label="high",
        reader_low_confidence=False,
        summary_text="Follow-up prompt test summary.",
        key_decisions=(),
        key_actions=key_actions,
        notable_topics=(),
        published_at="2026-03-09T12:06:00Z",
        claims=claims,
        structured_relevance=structured_relevance,
        additive_blocks=None,
    )


def _claim_with_v2_evidence(
    *,
    claim_id: str,
    claim_text: str,
    evidence_id: str,
    excerpt: str,
    artifact_id: str = "artifact-follow-up-1",
    document_kind: str = "minutes",
    section_path: str = "minutes.section.4",
    char_start: int | None = 10,
    char_end: int | None = 90,
    precision: str = "offset",
    confidence: str = "high",
) -> MeetingDetailClaim:
    return MeetingDetailClaim(
        id=claim_id,
        claim_order=1,
        claim_text=claim_text,
        evidence=(
            MeetingDetailEvidencePointer(
                id=evidence_id,
                artifact_id=artifact_id,
                source_document_url="https://example.org/minutes/follow-up-test.pdf",
                section_ref=section_path,
                char_start=char_start,
                char_end=char_end,
                excerpt=excerpt,
                document_id=f"doc-{evidence_id}",
                span_id=f"span-{evidence_id}",
                document_kind=document_kind,
                section_path=section_path,
                precision=precision,
                confidence=confidence,
            ),
        ),
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


def test_meeting_detail_flag_off_omits_resident_relevance_fields_when_additive_blocks_are_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")
    client = _client_with_configured_cities(monkeypatch, secret="resident-flag-off-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-resident-flag-off", secret="resident-flag-off-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-resident-flag-off",
        meeting_uid="uid-detail-resident-flag-off",
        title="Resident Relevance Flag Off Meeting",
        created_at="2026-03-09 12:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-publish-detail-resident-flag-off",
        run_id="run-detail-resident-flag-off",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-resident-flag-off",
        metadata={
            "structured_relevance": {
                "subject": {"value": "North Gateway rezoning application", "confidence": "high"},
                "impact_tags": [{"tag": "land_use", "confidence": "high"}],
            },
            "additive_blocks": {
                "planned": {
                    "items": [
                        {
                            "planned_id": "planned-resident-off-1",
                            "title": "North Gateway rezoning application",
                            "subject": {"value": "North Gateway rezoning application", "confidence": "high"},
                            "impact_tags": [{"tag": "land_use", "confidence": "high"}],
                        }
                    ]
                },
                "outcomes": {
                    "items": [
                        {
                            "outcome_id": "outcome-resident-off-1",
                            "title": "North Gateway rezoning approved",
                            "action": {"value": "approved", "confidence": "high"},
                            "impact_tags": [{"tag": "housing", "confidence": "high"}],
                        }
                    ]
                },
                "planned_outcome_mismatches": {
                    "summary": {"total": 0, "high": 0, "medium": 0, "low": 0},
                    "items": [],
                },
            }
        },
    )
    _insert_publication(
        client,
        publication_id="pub-detail-resident-flag-off",
        meeting_id="meeting-detail-resident-flag-off",
        publication_status="processed",
        confidence_label="high",
        summary_text="Resident relevance should remain hidden while the ST-033 flag is off.",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-09T12:05:00Z",
        publish_stage_outcome_id="outcome-publish-detail-resident-flag-off",
    )

    response = client.get("/v1/meetings/meeting-detail-resident-flag-off", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert "structured_relevance" not in payload
    assert "subject" not in payload["planned"]["items"][0]
    assert "impact_tags" not in payload["planned"]["items"][0]
    assert "action" not in payload["outcomes"]["items"][0]
    assert "impact_tags" not in payload["outcomes"]["items"][0]


def test_meeting_detail_flag_on_exposes_normalized_resident_relevance_fields_from_additive_blocks(monkeypatch) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")
    monkeypatch.setenv("ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED", "true")
    client = _client_with_configured_cities(monkeypatch, secret="resident-flag-on-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-resident-flag-on", secret="resident-flag-on-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-detail-resident-flag-on",
        meeting_uid="uid-detail-resident-flag-on",
        title="Resident Relevance Flag On Meeting",
        created_at="2026-03-09 13:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-publish-detail-resident-flag-on",
        run_id="run-detail-resident-flag-on",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-detail-resident-flag-on",
        metadata={
            "structured_relevance": {
                "subject": {
                    "value": " Main Street paving contract ",
                    "confidence": "HIGH",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-structured-2",
                            "document_id": "doc-structured-1",
                            "artifact_id": "artifact-structured-1",
                            "document_kind": "minutes",
                            "section_path": "minutes.section.7",
                            "page_start": 7,
                            "page_end": 7,
                            "char_start": 40,
                            "char_end": 110,
                            "precision": "offset",
                            "confidence": "high",
                            "excerpt": "Council approved the Main Street paving contract.",
                        },
                        {
                            "evidence_id": "ev-structured-1",
                            "document_id": "doc-structured-2",
                            "artifact_id": "artifact-structured-2",
                            "document_kind": "agenda",
                            "section_path": "agenda.items.4",
                            "page_start": 2,
                            "page_end": 2,
                            "char_start": None,
                            "char_end": None,
                            "precision": "section",
                            "confidence": "medium",
                            "excerpt": "Consider award of the Main Street paving contract.",
                        },
                    ],
                },
                "impact_tags": [
                    {"tag": "land_use", "confidence": "bad-value"},
                    {
                        "tag": "traffic",
                        "confidence": "medium",
                        "evidence_references_v2": [
                            {
                                "evidence_id": "ev-impact-2",
                                "document_id": "doc-impact-2",
                                "artifact_id": "artifact-impact-2",
                                "document_kind": "minutes",
                                "section_path": "minutes.section.7",
                                "page_start": 7,
                                "page_end": 7,
                                "char_start": 40,
                                "char_end": 110,
                                "precision": "offset",
                                "confidence": "high",
                                "excerpt": "Council approved the Main Street paving contract.",
                            },
                            {
                                "evidence_id": "ev-impact-1",
                                "document_id": "doc-impact-1",
                                "artifact_id": "artifact-impact-1",
                                "document_kind": "agenda",
                                "section_path": "agenda.items.4",
                                "page_start": 2,
                                "page_end": 2,
                                "char_start": None,
                                "char_end": None,
                                "precision": "section",
                                "confidence": "medium",
                                "excerpt": "Consider award of the Main Street paving contract.",
                            },
                        ],
                    },
                ],
            },
            "additive_blocks": {
                "planned": {
                    "items": [
                        {
                            "planned_id": "planned-resident-on-1",
                            "title": "Main Street paving contract",
                            "subject": {"value": " Main Street paving contract ", "confidence": "HIGH"},
                            "impact_tags": [
                                {"tag": "traffic", "confidence": "medium"},
                                {"tag": "unknown"},
                            ],
                        }
                    ]
                },
                "outcomes": {
                    "items": [
                        {
                            "outcome_id": "outcome-resident-on-1",
                            "title": "Main Street paving contract approved",
                            "action": {"value": "approved", "confidence": "HIGH"},
                            "impact_tags": [
                                {"tag": "land_use", "confidence": "bad-value"},
                                {"tag": "housing", "confidence": "high"},
                            ],
                        }
                    ]
                },
                "planned_outcome_mismatches": {
                    "summary": {"total": 0, "high": 0, "medium": 0, "low": 0},
                    "items": [],
                },
            }
        },
    )
    _insert_publication(
        client,
        publication_id="pub-detail-resident-flag-on",
        meeting_id="meeting-detail-resident-flag-on",
        publication_status="processed",
        confidence_label="high",
        summary_text="Resident relevance should be exposed only while the ST-033 flag is on.",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-09T13:05:00Z",
        publish_stage_outcome_id="outcome-publish-detail-resident-flag-on",
    )

    response = client.get("/v1/meetings/meeting-detail-resident-flag-on", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_relevance"] == {
        "subject": {
            "value": "Main Street paving contract",
            "confidence": "high",
            "evidence_references_v2": [
                {
                    "evidence_id": "ev-structured-2",
                    "document_id": "doc-structured-1",
                    "artifact_id": "artifact-structured-1",
                    "document_kind": "minutes",
                    "section_path": "minutes.section.7",
                    "page_start": 7,
                    "page_end": 7,
                    "char_start": 40,
                    "char_end": 110,
                    "precision": "offset",
                    "confidence": "high",
                    "excerpt": "Council approved the Main Street paving contract.",
                },
                {
                    "evidence_id": "ev-structured-1",
                    "document_id": "doc-structured-2",
                    "artifact_id": "artifact-structured-2",
                    "document_kind": "agenda",
                    "section_path": "agenda.items.4",
                    "page_start": 2,
                    "page_end": 2,
                    "char_start": None,
                    "char_end": None,
                    "precision": "section",
                    "confidence": "medium",
                    "excerpt": "Consider award of the Main Street paving contract.",
                },
            ],
        },
        "impact_tags": [
            {
                "tag": "traffic",
                "confidence": "medium",
                "evidence_references_v2": [
                    {
                        "evidence_id": "ev-impact-2",
                        "document_id": "doc-impact-2",
                        "artifact_id": "artifact-impact-2",
                        "document_kind": "minutes",
                        "section_path": "minutes.section.7",
                        "page_start": 7,
                        "page_end": 7,
                        "char_start": 40,
                        "char_end": 110,
                        "precision": "offset",
                        "confidence": "high",
                        "excerpt": "Council approved the Main Street paving contract.",
                    },
                    {
                        "evidence_id": "ev-impact-1",
                        "document_id": "doc-impact-1",
                        "artifact_id": "artifact-impact-1",
                        "document_kind": "agenda",
                        "section_path": "agenda.items.4",
                        "page_start": 2,
                        "page_end": 2,
                        "char_start": None,
                        "char_end": None,
                        "precision": "section",
                        "confidence": "medium",
                        "excerpt": "Consider award of the Main Street paving contract.",
                    },
                ],
            },
            {"tag": "land_use"},
        ],
    }
    assert payload["planned"]["items"][0]["subject"] == {
        "value": "Main Street paving contract",
        "confidence": "high",
    }
    assert payload["planned"]["items"][0]["impact_tags"] == [{"tag": "traffic", "confidence": "medium"}]
    assert payload["outcomes"]["items"][0]["action"] == {
        "value": "approved",
        "confidence": "high",
    }
    assert payload["outcomes"]["items"][0]["impact_tags"] == [
        {"tag": "housing", "confidence": "high"},
        {"tag": "land_use"},
    ]


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


@pytest.mark.parametrize(
    "fixture_id",
    [
        "st033-flag-on-full-structured-relevance",
        "st033-flag-on-sparse-structured-relevance",
        "st033-flag-on-legacy-structured-relevance-omitted",
    ],
)
def test_st033_meeting_detail_projection_matches_contract_fixture_for_nominal_sparse_and_missing_data(
    monkeypatch,
    fixture_id: str,
) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")
    monkeypatch.setenv("ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED", "true")

    scenario = _load_st033_contract_scenario(fixture_id)
    payload = cast(dict[str, Any], scenario["payload"])

    client = _client_with_configured_cities(monkeypatch, secret=f"{fixture_id}-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token(f"user-{fixture_id}", secret=f"{fixture_id}-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _seed_st033_contract_scenario(
        client,
        scenario=scenario,
        scramble_projection_ordering=True,
    )

    first_response = client.get(f"/v1/meetings/{payload['id']}", headers=headers)
    second_response = client.get(f"/v1/meetings/{payload['id']}", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == _with_reader_context(payload)
    assert second_response.json() == _with_reader_context(payload)


@pytest.mark.parametrize(
    "fixture_id",
    [
        "st033-flag-off-baseline-with-st027-blocks",
        "st033-flag-on-full-structured-relevance",
        "st033-flag-on-sparse-structured-relevance",
        "st033-flag-on-legacy-structured-relevance-omitted",
    ],
)
def test_st033_meeting_detail_flag_state_parity_matches_fixture_when_resident_relevance_is_ignored(
    monkeypatch,
    fixture_id: str,
) -> None:
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_FIELDS_ENABLED", "true")
    monkeypatch.setenv("ST022_API_ADDITIVE_V1_BLOCKS", "planned,outcomes,planned_outcome_mismatches")

    scenario = _load_st033_contract_scenario(fixture_id)
    payload = cast(dict[str, Any], scenario["payload"])

    monkeypatch.setenv("ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED", "true")
    client_flag_on = _client_with_configured_cities(
        monkeypatch,
        secret=f"{fixture_id}-flag-on-secret",
        supported_city_ids=PILOT_CITY_ID,
    )
    token_flag_on = _issue_token(
        f"user-{fixture_id}-flag-on",
        secret=f"{fixture_id}-flag-on-secret",
        expires_in_seconds=300,
    )
    headers_flag_on = {"Authorization": f"Bearer {token_flag_on}"}
    _set_home_city(client_flag_on, headers=headers_flag_on)
    _seed_st033_contract_scenario(
        client_flag_on,
        scenario=scenario,
        scramble_projection_ordering=True,
    )

    flag_on_response = client_flag_on.get(f"/v1/meetings/{payload['id']}", headers=headers_flag_on)

    monkeypatch.setenv("ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED", "false")
    client_flag_off = _client_with_configured_cities(
        monkeypatch,
        secret=f"{fixture_id}-flag-off-secret",
        supported_city_ids=PILOT_CITY_ID,
    )
    token_flag_off = _issue_token(
        f"user-{fixture_id}-flag-off",
        secret=f"{fixture_id}-flag-off-secret",
        expires_in_seconds=300,
    )
    headers_flag_off = {"Authorization": f"Bearer {token_flag_off}"}
    _set_home_city(client_flag_off, headers=headers_flag_off)
    _seed_st033_contract_scenario(
        client_flag_off,
        scenario=scenario,
        scramble_projection_ordering=True,
    )

    flag_off_response = client_flag_off.get(f"/v1/meetings/{payload['id']}", headers=headers_flag_off)

    assert flag_on_response.status_code == 200
    assert flag_off_response.status_code == 200

    expected_flag_on = _with_reader_context(payload)
    expected_flag_off = cast(dict[str, Any], _strip_st033_resident_relevance_fields(expected_flag_on))

    assert flag_on_response.json() == expected_flag_on
    assert flag_off_response.json() == expected_flag_off
    assert _strip_st033_resident_relevance_fields(flag_on_response.json()) == flag_off_response.json()


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


def test_meeting_detail_resident_relevance_flag_off_scrubs_top_level_and_item_level_fields() -> None:
    payload = _merge_resident_relevance_fields(
        payload={
            "id": "meeting-detail-resident-guard",
            "structured_relevance": {
                "subject": {"value": "North Gateway rezoning application", "confidence": "high"},
                "impact_tags": [{"tag": "land_use", "confidence": "high"}],
            },
            "planned": {
                "items": [
                    {
                        "planned_id": "planned-1",
                        "subject": {"value": "North Gateway rezoning application", "confidence": "high"},
                    }
                ]
            },
            "outcomes": {
                "items": [
                    {
                        "outcome_id": "outcome-1",
                        "action": {"value": "approved", "confidence": "high"},
                        "impact_tags": [{"tag": "housing", "confidence": "high"}],
                    }
                ]
            },
        },
        resident_relevance_api_settings=MeetingDetailResidentRelevanceApiSettings(enabled=False),
    )

    assert "structured_relevance" not in payload
    assert "subject" not in payload["planned"]["items"][0]
    assert "action" not in payload["outcomes"]["items"][0]
    assert "impact_tags" not in payload["outcomes"]["items"][0]


def test_meeting_detail_resident_relevance_flag_on_keeps_only_normalized_supported_fields() -> None:
    payload = _merge_resident_relevance_fields(
        payload={
            "id": "meeting-detail-resident-guard",
            "structured_relevance": {
                "subject": {
                    "value": " Main Street paving contract ",
                    "confidence": "HIGH",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-1",
                            "document_id": "doc-1",
                            "artifact_id": "artifact-1",
                            "document_kind": "minutes",
                            "section_path": "minutes.section.2",
                            "page_start": 2,
                            "page_end": 2,
                            "char_start": 10,
                            "char_end": 40,
                            "precision": "offset",
                            "confidence": "high",
                            "excerpt": "Council approved the Main Street paving contract.",
                        }
                    ],
                },
                "impact_tags": [
                    {"tag": "land_use", "confidence": "bad"},
                    {"tag": "traffic", "confidence": "medium"},
                ],
            },
            "planned": {
                "items": [
                    {
                        "planned_id": "planned-1",
                        "subject": {"value": "", "confidence": "high"},
                        "impact_tags": [{"tag": "unsupported"}],
                    }
                ]
            },
        },
        resident_relevance_api_settings=MeetingDetailResidentRelevanceApiSettings(enabled=True),
    )

    assert payload["structured_relevance"] == {
        "subject": {
            "value": "Main Street paving contract",
            "confidence": "high",
            "evidence_references_v2": [
                {
                    "evidence_id": "ev-1",
                    "document_id": "doc-1",
                    "artifact_id": "artifact-1",
                    "document_kind": "minutes",
                    "section_path": "minutes.section.2",
                    "page_start": 2,
                    "page_end": 2,
                    "char_start": 10,
                    "char_end": 40,
                    "precision": "offset",
                    "confidence": "high",
                    "excerpt": "Council approved the Main Street paving contract.",
                }
            ],
        },
        "impact_tags": [
            {"tag": "traffic", "confidence": "medium"},
            {"tag": "land_use"},
        ],
    }
    assert payload["planned"]["items"][0] == {"planned_id": "planned-1"}


def test_follow_up_prompt_suggestions_omit_all_prompts_when_top_level_structured_relevance_is_missing() -> None:
    detail = _meeting_detail_with_follow_up_prompt_inputs(
        structured_relevance=None,
        key_actions=("Staff will publish the ordinance by April 15, 2026.",),
        claims=(
            _claim_with_v2_evidence(
                claim_id="claim-follow-up-omit-1",
                claim_text="Staff will publish the ordinance by April 15, 2026.",
                evidence_id="ev-follow-up-omit-1",
                excerpt="Staff will publish the ordinance by April 15, 2026.",
            ),
        ),
    )

    assert _build_follow_up_prompt_suggestions(detail) == []


def test_follow_up_prompt_suggestions_follow_split_rules_for_mixed_scale_phrase() -> None:
    detail = _meeting_detail_with_follow_up_prompt_inputs(
        structured_relevance={
            "subject": {
                "value": "North Gateway rezoning application",
                "confidence": "high",
                "evidence_references_v2": [
                    {
                        "evidence_id": "ev-follow-up-scale-subject",
                        "document_id": "doc-follow-up-scale-subject",
                        "artifact_id": "artifact-follow-up-scale-subject",
                        "document_kind": "minutes",
                        "section_path": "minutes.section.4",
                        "page_start": None,
                        "page_end": None,
                        "char_start": 12,
                        "char_end": 80,
                        "precision": "offset",
                        "confidence": "high",
                        "excerpt": "North Gateway rezoning application covering 142 acres by June 2027.",
                    }
                ],
            },
            "scale": {
                "value": "142 acres by June 2027",
                "confidence": "high",
                "evidence_references_v2": [
                    {
                        "evidence_id": "ev-follow-up-scale-1",
                        "document_id": "doc-follow-up-scale-1",
                        "artifact_id": "artifact-follow-up-scale-1",
                        "document_kind": "minutes",
                        "section_path": "minutes.section.4",
                        "page_start": None,
                        "page_end": None,
                        "char_start": 12,
                        "char_end": 80,
                        "precision": "offset",
                        "confidence": "high",
                        "excerpt": "North Gateway rezoning application covering 142 acres by June 2027.",
                    }
                ],
            },
        },
        key_actions=(),
        claims=(),
    )

    prompts = _build_follow_up_prompt_suggestions(detail)

    assert [prompt["prompt_id"] for prompt in prompts] == ["project_identity", "scale"]
    assert prompts[1]["answer"] == "The scale in the record is 142 acres by June 2027."


def test_meeting_detail_follow_up_prompt_flag_off_preserves_route_parity(monkeypatch) -> None:
    payload = _merge_follow_up_prompt_suggestions(
        payload={
            "id": "meeting-follow-up-flag-off",
            "suggested_prompts": [{"prompt_id": "project_identity"}],
        },
        detail=_meeting_detail_with_follow_up_prompt_inputs(
            structured_relevance={
                "subject": {
                    "value": "North Gateway rezoning application",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-follow-up-flag-off",
                            "document_id": "doc-follow-up-flag-off",
                            "artifact_id": "artifact-follow-up-flag-off",
                            "document_kind": "minutes",
                            "section_path": "minutes.section.4",
                            "page_start": None,
                            "page_end": None,
                            "char_start": 12,
                            "char_end": 80,
                            "precision": "offset",
                            "confidence": "high",
                            "excerpt": "North Gateway rezoning application.",
                        }
                    ],
                }
            },
            key_actions=(),
            claims=(),
        ),
        follow_up_prompts_api_settings=MeetingDetailFollowUpPromptsApiSettings(enabled=False),
    )

    assert payload == {"id": "meeting-follow-up-flag-off"}


def test_meeting_detail_follow_up_prompt_merge_drops_stale_prompt_shell_when_no_grounded_answers_exist() -> None:
    payload = _merge_follow_up_prompt_suggestions(
        payload={
            "id": "meeting-follow-up-no-grounding",
            "summary": "Discussion of future work with no grounded follow-up answers.",
            "suggested_prompts": [
                {
                    "prompt_id": "project_identity",
                    "prompt": "What project or item is this about?",
                    "answer": "Placeholder answer.",
                    "evidence_references_v2": [],
                }
            ],
        },
        detail=_meeting_detail_with_follow_up_prompt_inputs(
            structured_relevance={
                "scale": {
                    "value": "next week",
                    "confidence": "high",
                }
            },
            key_actions=("Operator replay completed.",),
            claims=(
                _claim_with_v2_evidence(
                    claim_id="claim-follow-up-no-grounding-1",
                    claim_text="Operator replay completed.",
                    evidence_id="ev-follow-up-no-grounding-1",
                    excerpt="Operator replay completed.",
                ),
            ),
        ),
        follow_up_prompts_api_settings=MeetingDetailFollowUpPromptsApiSettings(enabled=True),
    )

    assert payload == {
        "id": "meeting-follow-up-no-grounding",
        "summary": "Discussion of future work with no grounded follow-up answers.",
    }


def test_meeting_detail_follow_up_prompts_are_present_deterministic_and_evidence_backed_when_flag_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ST035_API_FOLLOW_UP_PROMPTS_ENABLED", "true")

    client = _client_with_configured_cities(monkeypatch, secret="follow-up-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-follow-up", secret="follow-up-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-follow-up-enabled",
        meeting_uid="uid-follow-up-enabled",
        title="Follow Up Enabled Meeting",
        created_at="2026-03-09 14:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-follow-up-enabled",
        run_id="run-follow-up-enabled",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-follow-up-enabled",
        metadata={
            "structured_relevance": {
                "subject": {
                    "value": " North Gateway rezoning application ",
                    "confidence": "HIGH",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-follow-up-subject-2",
                            "document_id": "doc-follow-up-subject-2",
                            "artifact_id": "artifact-follow-up-subject-2",
                            "document_kind": "minutes",
                            "section_path": "minutes.section.4",
                            "page_start": None,
                            "page_end": None,
                            "char_start": 18,
                            "char_end": 122,
                            "precision": "offset",
                            "confidence": "high",
                            "excerpt": "Council approved the North Gateway rezoning application for the North Gateway District.",
                        },
                        {
                            "evidence_id": "ev-follow-up-subject-1",
                            "document_id": "doc-follow-up-subject-1",
                            "artifact_id": "artifact-follow-up-subject-1",
                            "document_kind": "agenda",
                            "section_path": "agenda.items.7",
                            "page_start": 5,
                            "page_end": 5,
                            "char_start": None,
                            "char_end": None,
                            "precision": "section",
                            "confidence": "medium",
                            "excerpt": "Public hearing and action on the North Gateway rezoning application.",
                        },
                    ],
                },
                "location": {
                    "value": "North Gateway District",
                    "confidence": "high",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-follow-up-location-1",
                            "document_id": "doc-follow-up-location-1",
                            "artifact_id": "artifact-follow-up-location-1",
                            "document_kind": "minutes",
                            "section_path": "minutes.section.4",
                            "page_start": None,
                            "page_end": None,
                            "char_start": 60,
                            "char_end": 122,
                            "precision": "offset",
                            "confidence": "high",
                            "excerpt": "Council approved the North Gateway rezoning application for the North Gateway District.",
                        }
                    ],
                },
                "action": {
                    "value": "approved",
                    "confidence": "high",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-follow-up-action-1",
                            "document_id": "doc-follow-up-action-1",
                            "artifact_id": "artifact-follow-up-action-1",
                            "document_kind": "minutes",
                            "section_path": "minutes.section.4",
                            "page_start": None,
                            "page_end": None,
                            "char_start": 18,
                            "char_end": 40,
                            "precision": "offset",
                            "confidence": "high",
                            "excerpt": "Council approved the North Gateway rezoning application for the North Gateway District.",
                        }
                    ],
                },
                "scale": {
                    "value": "142 acres and 893 units",
                    "confidence": "high",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-follow-up-scale-1",
                            "document_id": "doc-follow-up-scale-1",
                            "artifact_id": "artifact-follow-up-scale-1",
                            "document_kind": "minutes",
                            "section_path": "minutes.section.5",
                            "page_start": 6,
                            "page_end": 6,
                            "char_start": 10,
                            "char_end": 62,
                            "precision": "offset",
                            "confidence": "high",
                            "excerpt": "The ordinance covers 142 acres and 893 units.",
                        }
                    ],
                },
            }
        },
    )
    _insert_publication(
        client,
        publication_id="pub-follow-up-enabled",
        meeting_id="meeting-follow-up-enabled",
        publication_status="processed",
        confidence_label="high",
        summary_text="Council approved the North Gateway rezoning application.",
        key_decisions_json='["Approved the North Gateway rezoning application."]',
        key_actions_json='["Staff will publish the ordinance by April 15, 2026.","Operator replay completed."]',
        notable_topics_json='["Land use"]',
        published_at="2026-03-09T14:05:00Z",
        publish_stage_outcome_id="outcome-follow-up-enabled",
    )
    _insert_claim(
        client,
        claim_id="claim-follow-up-enabled-1",
        publication_id="pub-follow-up-enabled",
        claim_order=1,
        claim_text="Staff will publish the ordinance by April 15, 2026.",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="pointer-follow-up-enabled-1",
        claim_id="claim-follow-up-enabled-1",
        artifact_id="artifact-follow-up-action-2",
        section_ref="minutes.section.7",
        char_start=40,
        char_end=112,
        excerpt="Staff will publish the ordinance by April 15, 2026.",
        document_id="doc-follow-up-action-2",
        span_id="span-follow-up-action-2",
        document_kind="minutes",
        section_path="minutes.section.7",
        precision="offset",
        confidence="high",
    )

    first_response = client.get("/v1/meetings/meeting-follow-up-enabled", headers=headers)
    second_response = client.get("/v1/meetings/meeting-follow-up-enabled", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_payload = first_response.json()
    second_payload = second_response.json()

    assert first_payload["suggested_prompts"] == second_payload["suggested_prompts"]
    assert [prompt["prompt_id"] for prompt in first_payload["suggested_prompts"]] == [
        "project_identity",
        "location",
        "disposition",
        "scale",
        "timeline",
        "next_step",
    ]
    assert [prompt["prompt"] for prompt in first_payload["suggested_prompts"]] == [
        "What project or item is this about?",
        "Where does this apply?",
        "What happened at this meeting?",
        "How large is it?",
        "What is the timeline?",
        "What happens next?",
    ]
    assert [prompt["answer"] for prompt in first_payload["suggested_prompts"]] == [
        "North Gateway rezoning application.",
        "It applies to North Gateway District.",
        "North Gateway rezoning application was approved.",
        "The scale in the record is 142 acres and 893 units.",
        "The timeline in the record is April 15, 2026.",
        "Staff will publish the ordinance by April 15, 2026.",
    ]
    assert all(prompt["evidence_references_v2"] for prompt in first_payload["suggested_prompts"])
    assert first_payload["suggested_prompts"][0]["evidence_references_v2"][0]["precision"] == "offset"
    assert first_payload["suggested_prompts"][0]["evidence_references_v2"][1]["precision"] == "section"


def test_meeting_detail_follow_up_prompts_omit_unsupported_answers_cleanly_when_flag_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ST035_API_FOLLOW_UP_PROMPTS_ENABLED", "true")

    client = _client_with_configured_cities(monkeypatch, secret="follow-up-omit-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token("user-follow-up-omit", secret="follow-up-omit-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _insert_meeting(
        client,
        meeting_id="meeting-follow-up-omit",
        meeting_uid="uid-follow-up-omit",
        title="Follow Up Omit Meeting",
        created_at="2026-03-09 15:00:00",
    )
    _insert_publish_stage_outcome(
        client,
        outcome_id="outcome-follow-up-omit",
        run_id="run-follow-up-omit",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-follow-up-omit",
        metadata={
            "structured_relevance": {
                "location": {
                    "value": "Main Street",
                    "confidence": "medium",
                    "evidence_references_v2": [
                        {
                            "evidence_id": "ev-follow-up-omit-location-1",
                            "document_id": "doc-follow-up-omit-location-1",
                            "artifact_id": "artifact-follow-up-omit-location-1",
                            "document_kind": "agenda",
                            "section_path": "agenda.items.4",
                            "page_start": 3,
                            "page_end": 3,
                            "char_start": None,
                            "char_end": None,
                            "precision": "section",
                            "confidence": "medium",
                            "excerpt": "Discussion of work on Main Street.",
                        }
                    ],
                },
                "scale": {
                    "value": "next week",
                    "confidence": "high"
                }
            }
        },
    )
    _insert_publication(
        client,
        publication_id="pub-follow-up-omit",
        meeting_id="meeting-follow-up-omit",
        publication_status="processed",
        confidence_label="medium",
        summary_text="Discussion of future work on Main Street.",
        key_decisions_json="[]",
        key_actions_json='["Operator replay completed."]',
        notable_topics_json='["Transportation"]',
        published_at="2026-03-09T15:05:00Z",
        publish_stage_outcome_id="outcome-follow-up-omit",
    )
    _insert_claim(
        client,
        claim_id="claim-follow-up-omit-1",
        publication_id="pub-follow-up-omit",
        claim_order=1,
        claim_text="Operator replay completed.",
    )
    _insert_evidence_pointer(
        client,
        pointer_id="pointer-follow-up-omit-1",
        claim_id="claim-follow-up-omit-1",
        artifact_id="artifact-follow-up-omit-action-1",
        section_ref="minutes.section.9",
        char_start=5,
        char_end=40,
        excerpt="Operator replay completed.",
        document_id="doc-follow-up-omit-action-1",
        span_id="span-follow-up-omit-action-1",
        document_kind="minutes",
        section_path="minutes.section.9",
        precision="offset",
        confidence="high",
    )

    response = client.get("/v1/meetings/meeting-follow-up-omit", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_prompts"] == [
        {
            "prompt_id": "location",
            "prompt": "Where does this apply?",
            "answer": "It applies to Main Street.",
            "evidence_references_v2": [
                {
                    "evidence_id": "ev-follow-up-omit-location-1",
                    "document_id": "doc-follow-up-omit-location-1",
                    "artifact_id": "artifact-follow-up-omit-location-1",
                    "document_kind": "agenda",
                    "section_path": "agenda.items.4",
                    "page_start": 3,
                    "page_end": 3,
                    "char_start": None,
                    "char_end": None,
                    "precision": "section",
                    "confidence": "medium",
                    "excerpt": "Discussion of work on Main Street.",
                }
            ],
        }
    ]


@pytest.mark.parametrize(
    "fixture_id",
    [
        "st035-flag-on-supported-prompts",
        "st035-flag-on-unsupported-omits-prompt-block",
    ],
)
def test_st035_meeting_detail_matches_contract_fixture_when_follow_up_prompt_flag_enabled(
    monkeypatch,
    fixture_id: str,
) -> None:
    monkeypatch.setenv("ST035_API_FOLLOW_UP_PROMPTS_ENABLED", "true")

    scenario = _load_st035_contract_scenario(fixture_id)
    payload = cast(dict[str, Any], scenario["payload"])

    client = _client_with_configured_cities(monkeypatch, secret=f"{fixture_id}-secret", supported_city_ids=PILOT_CITY_ID)
    token = _issue_token(f"user-{fixture_id}", secret=f"{fixture_id}-secret", expires_in_seconds=300)
    headers = {"Authorization": f"Bearer {token}"}
    _set_home_city(client, headers=headers)

    _seed_st035_contract_scenario(client, scenario=scenario)

    first_response = client.get(f"/v1/meetings/{payload['id']}", headers=headers)
    second_response = client.get(f"/v1/meetings/{payload['id']}", headers=headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == _with_reader_context(payload)
    assert second_response.json() == _with_reader_context(payload)


def test_st035_meeting_detail_flag_state_parity_matches_fixture_when_follow_up_prompts_are_ignored(monkeypatch) -> None:
    scenario = _load_st035_contract_scenario("st035-flag-on-supported-prompts")
    payload = cast(dict[str, Any], scenario["payload"])

    monkeypatch.setenv("ST035_API_FOLLOW_UP_PROMPTS_ENABLED", "true")
    client_flag_on = _client_with_configured_cities(
        monkeypatch,
        secret="st035-flag-on-secret",
        supported_city_ids=PILOT_CITY_ID,
    )
    token_flag_on = _issue_token("user-st035-flag-on", secret="st035-flag-on-secret", expires_in_seconds=300)
    headers_flag_on = {"Authorization": f"Bearer {token_flag_on}"}
    _set_home_city(client_flag_on, headers=headers_flag_on)
    _seed_st035_contract_scenario(client_flag_on, scenario=scenario)

    flag_on_response = client_flag_on.get(f"/v1/meetings/{payload['id']}", headers=headers_flag_on)

    monkeypatch.setenv("ST035_API_FOLLOW_UP_PROMPTS_ENABLED", "false")
    client_flag_off = _client_with_configured_cities(
        monkeypatch,
        secret="st035-flag-off-secret",
        supported_city_ids=PILOT_CITY_ID,
    )
    token_flag_off = _issue_token("user-st035-flag-off", secret="st035-flag-off-secret", expires_in_seconds=300)
    headers_flag_off = {"Authorization": f"Bearer {token_flag_off}"}
    _set_home_city(client_flag_off, headers=headers_flag_off)
    _seed_st035_contract_scenario(client_flag_off, scenario=scenario)

    flag_off_response = client_flag_off.get(f"/v1/meetings/{payload['id']}", headers=headers_flag_off)

    assert flag_on_response.status_code == 200
    assert flag_off_response.status_code == 200

    expected_flag_on = _with_reader_context(payload)
    expected_flag_off = cast(dict[str, Any], _strip_st035_follow_up_prompt_fields(expected_flag_on))

    assert flag_on_response.json() == expected_flag_on
    assert flag_off_response.json() == expected_flag_off
    assert _strip_st035_follow_up_prompt_fields(flag_on_response.json()) == flag_off_response.json()
