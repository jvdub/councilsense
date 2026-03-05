from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from councilsense.app.bundle_state_tracking import (
    initialize_bundle_state,
    source_outcome_from_dedupe_decision,
    wire_source_outcomes,
)
from councilsense.app.meeting_bundle_planner import MeetingCandidate, SourceRegistration, plan_meeting_bundles
from councilsense.app.source_scoped_idempotency import SourcePayloadCandidate, dedupe_source_payloads


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st023_pilot_city_smoke_fixture.json"


def _load_fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_fixture_path().read_text(encoding="utf-8")))


def _build_candidates(payload: list[dict[str, Any]]) -> tuple[MeetingCandidate, ...]:
    return tuple(
        MeetingCandidate(
            meeting_id=str(item["meeting_id"]),
            title=str(item["title"]),
            candidate_url=str(item["candidate_url"]),
            meeting_date_iso=cast(str | None, item.get("meeting_date_iso")),
            score=int(item["score"]),
        )
        for item in payload
    )


def _build_registrations(payload: list[dict[str, Any]]) -> tuple[SourceRegistration, ...]:
    return tuple(
        SourceRegistration(
            source_id=str(item["source_id"]),
            source_type=str(item["source_type"]),
            source_url=str(item["source_url"]),
            enabled=bool(item.get("enabled", True)),
        )
        for item in payload
    )


def _build_payload_candidates(payload: list[dict[str, Any]]) -> tuple[SourcePayloadCandidate, ...]:
    return tuple(
        SourcePayloadCandidate(
            source_id=str(item["source_id"]),
            source_type=str(item["source_type"]),
            source_url=str(item["source_url"]),
            source_revision=str(item["source_revision"]),
            source_checksum=str(item["source_checksum"]),
            artifact_uri=cast(str | None, item.get("artifact_uri")),
        )
        for item in payload
    )


def test_st023_pilot_city_smoke_fixture_minutes_plus_supplemental_path_is_deterministic() -> None:
    fixture = _load_fixture()

    assert fixture["schema_version"] == "st023-pilot-city-smoke-fixture-v1"
    assert fixture["fixture_id"] == "st023-pilot-city-minutes-plus-agenda"

    city_id = str(fixture["city_id"])
    planner_result = plan_meeting_bundles(
        city_id=city_id,
        meeting_candidates=_build_candidates(cast(list[dict[str, Any]], fixture["meeting_candidates"])),
        source_registrations=_build_registrations(cast(list[dict[str, Any]], fixture["source_registrations"])),
    )

    assert len(planner_result.bundles) == 1
    bundle = planner_result.bundles[0]
    assert bundle.city_id == city_id

    seen_document_idempotency: set[str] = set()
    seen_artifact_uris: set[str] = set()
    seen_publication_scopes: set[tuple[str, tuple[str, ...]]] = set()

    for run in cast(list[dict[str, Any]], fixture["runs"]):
        dedupe_result = dedupe_source_payloads(
            city_id=city_id,
            meeting_id=bundle.meeting_id,
            candidates=_build_payload_candidates(cast(list[dict[str, Any]], run["source_payload_candidates"])),
        )
        expected = cast(dict[str, Any], run["expected"])

        assert len(dedupe_result.accepted) == int(expected["accepted_count"])
        assert len(dedupe_result.suppressed) == int(expected["suppressed_count"])

        extract_outcomes = cast(dict[str, str], run["extract_outcomes"])
        state = initialize_bundle_state(bundle_plan=bundle)
        state = wire_source_outcomes(
            bundle_state=state,
            source_outcomes=tuple(
                source_outcome_from_dedupe_decision(
                    decision=decision,
                    extract_outcome=extract_outcomes.get(decision.source_type, "missing"),
                )
                for decision in dedupe_result.accepted
            ),
        )

        assert state.readiness == str(expected["readiness"])
        assert state.summary_outcome == str(expected["summary_outcome"])
        assert state.reason_codes == tuple(cast(list[str], expected["reason_codes"]))

        accepted_idempotency = {item.idempotency_key for item in dedupe_result.accepted}
        accepted_artifacts = {
            cast(str, item.linked_artifact_uri) for item in dedupe_result.accepted if item.linked_artifact_uri is not None
        }

        new_documents = accepted_idempotency - seen_document_idempotency
        new_artifacts = accepted_artifacts - seen_artifact_uris
        publication_scope = (bundle.bundle_id, tuple(sorted(accepted_idempotency)))
        new_publication_count = 0 if publication_scope in seen_publication_scopes else 1

        assert len(new_documents) == int(expected["new_documents_count"])
        assert len(new_artifacts) == int(expected["new_artifacts_count"])
        assert new_publication_count == int(expected["new_publications_count"])

        seen_document_idempotency.update(accepted_idempotency)
        seen_artifact_uris.update(accepted_artifacts)
        seen_publication_scopes.add(publication_scope)
