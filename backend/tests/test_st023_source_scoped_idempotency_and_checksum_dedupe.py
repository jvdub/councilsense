from __future__ import annotations

import hashlib

from councilsense.app.source_scoped_idempotency import (
    SOURCE_SCOPED_DEDUPE_KEY_VERSION,
    SourcePayloadCandidate,
    build_source_scoped_dedupe_key,
    build_source_scoped_ingest_idempotency_key,
    compute_source_payload_checksum,
    dedupe_source_payloads,
)
from councilsense.app.st022_stage_contracts import ST022_IDEMPOTENCY_KEY_VERSION


def test_source_scoped_ingest_idempotency_key_is_deterministic_and_source_scoped() -> None:
    one = build_source_scoped_ingest_idempotency_key(
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-2026-03-04-regular",
        source_type="Minutes",
        source_revision="rev-2026-03-04",
        source_checksum="sha256:abc123",
    )
    two = build_source_scoped_ingest_idempotency_key(
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-2026-03-04-regular",
        source_type="minutes",
        source_revision="rev-2026-03-04",
        source_checksum="sha256:abc123",
    )

    assert one == two
    assert one.startswith(f"{ST022_IDEMPOTENCY_KEY_VERSION}:ingest:")
    assert ":city=city-eagle-mountain-ut:" in one
    assert ":meeting=meeting-2026-03-04-regular:" in one
    assert ":source=minutes:" in one
    assert one.endswith("checksum=sha256%3Aabc123")


def test_source_scoped_dedupe_key_is_stable_hash_of_idempotency_scope() -> None:
    dedupe_key = build_source_scoped_dedupe_key(
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-2026-03-04-regular",
        source_type="agenda",
        source_revision="rev-2026-03-04T12:00:00Z",
        source_checksum="sha256:payload-1",
    )
    idem = build_source_scoped_ingest_idempotency_key(
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-2026-03-04-regular",
        source_type="agenda",
        source_revision="rev-2026-03-04T12:00:00Z",
        source_checksum="sha256:payload-1",
    )

    expected_suffix = hashlib.sha256(idem.encode("utf-8")).hexdigest()
    assert dedupe_key == f"{SOURCE_SCOPED_DEDUPE_KEY_VERSION}:{expected_suffix}"


def test_duplicate_source_payloads_are_suppressed_deterministically_and_link_canonical_artifact() -> None:
    candidates = (
        SourcePayloadCandidate(
            source_id="src-minutes-secondary",
            source_type="minutes",
            source_url="https://example.org/minutes-secondary",
            source_revision="rev-2026-03-04",
            source_checksum="sha256:same-payload",
            artifact_uri="s3://bucket/minutes/secondary.txt",
        ),
        SourcePayloadCandidate(
            source_id="src-minutes-primary",
            source_type="minutes",
            source_url="https://example.org/minutes-primary",
            source_revision="rev-2026-03-04",
            source_checksum="sha256:same-payload",
            artifact_uri="s3://bucket/minutes/primary.txt",
        ),
        SourcePayloadCandidate(
            source_id="src-agenda",
            source_type="agenda",
            source_url="https://example.org/agenda",
            source_revision="rev-2026-03-04",
            source_checksum="sha256:different",
            artifact_uri="s3://bucket/agenda/1.txt",
        ),
    )

    first = dedupe_source_payloads(
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-2026-03-04-regular",
        candidates=candidates,
    )
    second = dedupe_source_payloads(
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-2026-03-04-regular",
        candidates=tuple(reversed(candidates)),
    )

    assert first == second
    assert len(first.accepted) == 2
    assert len(first.suppressed) == 1
    assert first.suppressed[0].outcome == "duplicate_suppressed"
    assert first.suppressed[0].linked_artifact_uri == first.accepted[1].linked_artifact_uri
    assert first.suppressed[0].idempotency_key == first.accepted[1].idempotency_key
    assert any(item.code == "source_payload_duplicate_suppressed" for item in first.diagnostics)


def test_compute_source_payload_checksum_uses_sha256_prefix_format() -> None:
    checksum = compute_source_payload_checksum(payload_bytes=b"sample-source-payload")
    assert checksum.startswith("sha256:")
    assert len(checksum) == len("sha256:") + 64
