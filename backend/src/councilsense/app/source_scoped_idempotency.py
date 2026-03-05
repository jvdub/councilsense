from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from councilsense.app.st022_stage_contracts import build_ingest_idempotency_key


SOURCE_SCOPED_DEDUPE_KEY_VERSION = "st023-source-dedupe-v1"


@dataclass(frozen=True)
class SourcePayloadCandidate:
    source_id: str
    source_type: str
    source_url: str
    source_revision: str
    source_checksum: str
    artifact_uri: str | None = None


@dataclass(frozen=True)
class SourcePayloadDecision:
    source_id: str
    source_type: str
    source_revision: str
    source_checksum: str
    idempotency_key: str
    dedupe_key: str
    outcome: Literal["accepted", "duplicate_suppressed"]
    linked_artifact_uri: str | None


@dataclass(frozen=True)
class SourcePayloadDedupeDiagnostic:
    code: str
    city_id: str
    meeting_id: str
    source_id: str
    source_type: str
    source_revision: str
    source_checksum: str
    idempotency_key: str
    dedupe_key: str
    outcome: Literal["accepted", "duplicate_suppressed"]
    detail: str


@dataclass(frozen=True)
class SourcePayloadDedupeResult:
    accepted: tuple[SourcePayloadDecision, ...]
    suppressed: tuple[SourcePayloadDecision, ...]
    diagnostics: tuple[SourcePayloadDedupeDiagnostic, ...]


def compute_source_payload_checksum(*, payload_bytes: bytes) -> str:
    if not payload_bytes:
        raise ValueError("payload_bytes must be non-empty")
    digest = hashlib.sha256(payload_bytes).hexdigest()
    return f"sha256:{digest}"


def build_source_scoped_ingest_idempotency_key(
    *,
    city_id: str,
    meeting_id: str,
    source_type: str,
    source_revision: str,
    source_checksum: str,
) -> str:
    normalized_source_type = source_type.strip().lower()
    return build_ingest_idempotency_key(
        city_id=city_id,
        meeting_id=meeting_id,
        source_type=normalized_source_type,
        source_revision=source_revision,
        source_checksum=source_checksum,
    )


def build_source_scoped_dedupe_key(
    *,
    city_id: str,
    meeting_id: str,
    source_type: str,
    source_revision: str,
    source_checksum: str,
) -> str:
    idempotency_key = build_source_scoped_ingest_idempotency_key(
        city_id=city_id,
        meeting_id=meeting_id,
        source_type=source_type,
        source_revision=source_revision,
        source_checksum=source_checksum,
    )
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"{SOURCE_SCOPED_DEDUPE_KEY_VERSION}:{digest}"


def dedupe_source_payloads(
    *,
    city_id: str,
    meeting_id: str,
    candidates: tuple[SourcePayloadCandidate, ...],
) -> SourcePayloadDedupeResult:
    normalized = [_normalize_candidate(item) for item in candidates]
    normalized.sort(
        key=lambda item: (
            item.source_type,
            item.source_revision,
            item.source_checksum,
            item.source_id,
            item.source_url,
            item.artifact_uri or "",
        )
    )

    accepted: list[SourcePayloadDecision] = []
    suppressed: list[SourcePayloadDecision] = []
    diagnostics: list[SourcePayloadDedupeDiagnostic] = []
    canonical_by_dedupe_key: dict[str, SourcePayloadDecision] = {}

    for candidate in normalized:
        idempotency_key = build_source_scoped_ingest_idempotency_key(
            city_id=city_id,
            meeting_id=meeting_id,
            source_type=candidate.source_type,
            source_revision=candidate.source_revision,
            source_checksum=candidate.source_checksum,
        )
        dedupe_key = build_source_scoped_dedupe_key(
            city_id=city_id,
            meeting_id=meeting_id,
            source_type=candidate.source_type,
            source_revision=candidate.source_revision,
            source_checksum=candidate.source_checksum,
        )

        canonical = canonical_by_dedupe_key.get(dedupe_key)
        if canonical is None:
            decision = SourcePayloadDecision(
                source_id=candidate.source_id,
                source_type=candidate.source_type,
                source_revision=candidate.source_revision,
                source_checksum=candidate.source_checksum,
                idempotency_key=idempotency_key,
                dedupe_key=dedupe_key,
                outcome="accepted",
                linked_artifact_uri=candidate.artifact_uri,
            )
            canonical_by_dedupe_key[dedupe_key] = decision
            accepted.append(decision)
            diagnostics.append(
                SourcePayloadDedupeDiagnostic(
                    code="source_payload_ingest_accepted",
                    city_id=city_id,
                    meeting_id=meeting_id,
                    source_id=candidate.source_id,
                    source_type=candidate.source_type,
                    source_revision=candidate.source_revision,
                    source_checksum=candidate.source_checksum,
                    idempotency_key=idempotency_key,
                    dedupe_key=dedupe_key,
                    outcome="accepted",
                    detail="source payload accepted as canonical entry for dedupe scope",
                )
            )
            continue

        decision = SourcePayloadDecision(
            source_id=candidate.source_id,
            source_type=candidate.source_type,
            source_revision=candidate.source_revision,
            source_checksum=candidate.source_checksum,
            idempotency_key=idempotency_key,
            dedupe_key=dedupe_key,
            outcome="duplicate_suppressed",
            linked_artifact_uri=canonical.linked_artifact_uri,
        )
        suppressed.append(decision)
        diagnostics.append(
            SourcePayloadDedupeDiagnostic(
                code="source_payload_duplicate_suppressed",
                city_id=city_id,
                meeting_id=meeting_id,
                source_id=candidate.source_id,
                source_type=candidate.source_type,
                source_revision=candidate.source_revision,
                source_checksum=candidate.source_checksum,
                idempotency_key=idempotency_key,
                dedupe_key=dedupe_key,
                outcome="duplicate_suppressed",
                detail=(
                    "duplicate payload suppressed; reusing canonical source artifact linkage"
                ),
            )
        )

    diagnostics.sort(
        key=lambda item: (
            item.code,
            item.source_type,
            item.source_revision,
            item.source_checksum,
            item.source_id,
            item.idempotency_key,
            item.dedupe_key,
        )
    )

    return SourcePayloadDedupeResult(
        accepted=tuple(accepted),
        suppressed=tuple(suppressed),
        diagnostics=tuple(diagnostics),
    )


def _normalize_candidate(candidate: SourcePayloadCandidate) -> SourcePayloadCandidate:
    source_id = candidate.source_id.strip()
    source_type = candidate.source_type.strip().lower()
    source_url = candidate.source_url.strip()
    source_revision = candidate.source_revision.strip()
    source_checksum = candidate.source_checksum.strip()
    artifact_uri = candidate.artifact_uri.strip() if isinstance(candidate.artifact_uri, str) else None

    if not source_id:
        raise ValueError("source_id must be non-empty")
    if not source_type:
        raise ValueError("source_type must be non-empty")
    if not source_url:
        raise ValueError("source_url must be non-empty")
    if not source_revision:
        raise ValueError("source_revision must be non-empty")
    if not source_checksum:
        raise ValueError("source_checksum must be non-empty")

    return SourcePayloadCandidate(
        source_id=source_id,
        source_type=source_type,
        source_url=source_url,
        source_revision=source_revision,
        source_checksum=source_checksum,
        artifact_uri=artifact_uri,
    )