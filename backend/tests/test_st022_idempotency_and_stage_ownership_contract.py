from __future__ import annotations

import pytest

from councilsense.app.st022_stage_contracts import (
    ST022_IDEMPOTENCY_KEY_VERSION,
    ST022_STAGE_OWNERSHIP_TABLE,
    build_extract_idempotency_key,
    build_ingest_idempotency_key,
    build_publish_idempotency_key,
    build_summarize_idempotency_key,
    stage_ownership_for,
)


def test_st022_ingest_and_extract_key_formats_are_deterministic() -> None:
    ingest_key_one = build_ingest_idempotency_key(
        city_id="city-seattle-wa",
        meeting_id="meeting-2026-03-04-regular",
        source_type="minutes",
        source_revision="rev-2026-03-04T09:30:00Z",
        source_checksum="sha256:111aaa",
    )
    ingest_key_two = build_ingest_idempotency_key(
        city_id="city-seattle-wa",
        meeting_id="meeting-2026-03-04-regular",
        source_type="minutes",
        source_revision="rev-2026-03-04T09:30:00Z",
        source_checksum="sha256:111aaa",
    )
    extract_key = build_extract_idempotency_key(
        city_id="city-seattle-wa",
        meeting_id="meeting-2026-03-04-regular",
        source_type="minutes",
        source_revision="rev-2026-03-04T09:30:00Z",
        artifact_checksum="sha256:extract-222bbb",
    )

    assert ingest_key_one == ingest_key_two
    assert ingest_key_one.startswith(f"{ST022_IDEMPOTENCY_KEY_VERSION}:ingest:")
    assert ":city=city-seattle-wa:" in ingest_key_one
    assert ":meeting=meeting-2026-03-04-regular:" in ingest_key_one
    assert ":source=minutes:" in ingest_key_one
    assert ":revision=rev-2026-03-04T09%3A30%3A00Z:" in ingest_key_one
    assert ingest_key_one.endswith("checksum=sha256%3A111aaa")

    assert extract_key.startswith(f"{ST022_IDEMPOTENCY_KEY_VERSION}:extract:")
    assert ":source=minutes:" in extract_key
    assert extract_key.endswith("checksum=sha256%3Aextract-222bbb")


def test_st022_summarize_and_publish_key_formats_cover_rerun_and_duplicate_cases() -> None:
    summarize_normal = build_summarize_idempotency_key(
        city_id="city-seattle-wa",
        meeting_id="meeting-2026-03-04-regular",
        bundle_revision="bundle-v1",
        source_coverage_checksum="sha256:coverage-aaa",
    )
    summarize_rerun_same_inputs = build_summarize_idempotency_key(
        city_id="city-seattle-wa",
        meeting_id="meeting-2026-03-04-regular",
        bundle_revision="bundle-v1",
        source_coverage_checksum="sha256:coverage-aaa",
    )
    summarize_duplicate_payload_different_revision = build_summarize_idempotency_key(
        city_id="city-seattle-wa",
        meeting_id="meeting-2026-03-04-regular",
        bundle_revision="bundle-v2",
        source_coverage_checksum="sha256:coverage-aaa",
    )

    publish_key = build_publish_idempotency_key(
        city_id="city-seattle-wa",
        meeting_id="meeting-2026-03-04-regular",
        publication_revision="pub-v1",
        summary_checksum="sha256:summary-zzz",
    )

    assert summarize_normal == summarize_rerun_same_inputs
    assert summarize_normal != summarize_duplicate_payload_different_revision
    assert summarize_normal.startswith(f"{ST022_IDEMPOTENCY_KEY_VERSION}:summarize:")
    assert ":bundle_revision=bundle-v1:" in summarize_normal
    assert summarize_normal.endswith("coverage_checksum=sha256%3Acoverage-aaa")

    assert publish_key.startswith(f"{ST022_IDEMPOTENCY_KEY_VERSION}:publish:")
    assert ":publication_revision=pub-v1:" in publish_key
    assert publish_key.endswith("summary_checksum=sha256%3Asummary-zzz")


def test_st022_idempotency_keys_reject_blank_components() -> None:
    with pytest.raises(ValueError, match="city must be non-empty"):
        build_ingest_idempotency_key(
            city_id=" ",
            meeting_id="meeting-1",
            source_type="minutes",
            source_revision="rev-1",
            source_checksum="sha256:1",
        )


def test_st022_stage_ownership_table_has_unambiguous_ordered_boundaries() -> None:
    assert [entry.stage for entry in ST022_STAGE_OWNERSHIP_TABLE] == [
        "ingest",
        "extract",
        "summarize",
        "publish",
    ]

    for stage in ("ingest", "extract", "summarize", "publish"):
        ownership = stage_ownership_for(stage)
        assert ownership.producer.strip()
        assert ownership.consumer.strip()
        assert ownership.persisted_handoff_state.strip()
        assert ownership.boundary.strip()
