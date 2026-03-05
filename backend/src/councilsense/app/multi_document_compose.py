from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Literal

from councilsense.app.meeting_bundle_planner import EXPECTED_SOURCE_TYPES
from councilsense.db import CanonicalDocumentRepository, CanonicalDocumentRecord


SourceCoverageStatus = Literal["present", "partial", "missing"]
ComposeSourceOrigin = Literal["canonical", "fallback_extract", "missing"]


@dataclass(frozen=True)
class ComposedSourceDocument:
    source_type: str
    source_origin: ComposeSourceOrigin
    coverage_status: SourceCoverageStatus
    text: str
    canonical_document_id: str | None
    revision_id: str | None
    revision_number: int | None
    extraction_status: str | None
    extracted_at: str | None
    span_count: int


@dataclass(frozen=True)
class SourceCoverageSummary:
    source_order: tuple[str, ...]
    statuses: dict[str, SourceCoverageStatus]
    canonical_source_types: tuple[str, ...]
    fallback_source_types: tuple[str, ...]
    partial_source_types: tuple[str, ...]
    missing_source_types: tuple[str, ...]
    available_source_types: tuple[str, ...]
    coverage_ratio: float
    coverage_checksum: str

    def to_metadata_payload(self) -> dict[str, object]:
        return {
            "source_order": list(self.source_order),
            "statuses": dict(self.statuses),
            "canonical_source_types": list(self.canonical_source_types),
            "fallback_source_types": list(self.fallback_source_types),
            "partial_source_types": list(self.partial_source_types),
            "missing_source_types": list(self.missing_source_types),
            "available_source_types": list(self.available_source_types),
            "coverage_ratio": self.coverage_ratio,
            "coverage_checksum": self.coverage_checksum,
        }


@dataclass(frozen=True)
class SummarizeComposeInput:
    meeting_id: str
    source_order: tuple[str, ...]
    sources: tuple[ComposedSourceDocument, ...]
    composed_text: str
    source_coverage: SourceCoverageSummary

    def to_stage_metadata_payload(self) -> dict[str, object]:
        source_payload = [
            {
                "source_type": source.source_type,
                "source_origin": source.source_origin,
                "coverage_status": source.coverage_status,
                "canonical_document_id": source.canonical_document_id,
                "revision_id": source.revision_id,
                "revision_number": source.revision_number,
                "extraction_status": source.extraction_status,
                "extracted_at": source.extracted_at,
                "span_count": source.span_count,
                "text_char_count": len(source.text),
            }
            for source in self.sources
        ]
        return {
            "meeting_id": self.meeting_id,
            "source_order": list(self.source_order),
            "sources": source_payload,
            "source_coverage": self.source_coverage.to_metadata_payload(),
        }


def assemble_summarize_compose_input(
    *,
    connection: sqlite3.Connection,
    meeting_id: str,
    fallback_source_type: str | None,
    fallback_text: str,
) -> SummarizeComposeInput:
    repository = CanonicalDocumentRepository(connection)
    documents = repository.list_documents_for_meeting(meeting_id=meeting_id)

    normalized_fallback_type = _normalize_source_type(fallback_source_type)
    normalized_fallback_text = " ".join(fallback_text.split())

    composed_sources: list[ComposedSourceDocument] = []
    for source_type in EXPECTED_SOURCE_TYPES:
        selected = _select_preferred_document(documents=documents, source_type=source_type)
        if selected is not None:
            canonical_text, span_count = _compose_document_text(
                connection=connection,
                canonical_document_id=selected.id,
            )
            prefer_fallback_text = (
                normalized_fallback_text
                and normalized_fallback_type is not None
                and normalized_fallback_type == source_type
            )
            composed_text = normalized_fallback_text if prefer_fallback_text else canonical_text
            status: SourceCoverageStatus = "present" if composed_text else "partial"
            composed_sources.append(
                ComposedSourceDocument(
                    source_type=source_type,
                    source_origin="canonical",
                    coverage_status=status,
                    text=composed_text,
                    canonical_document_id=selected.id,
                    revision_id=selected.revision_id,
                    revision_number=selected.revision_number,
                    extraction_status=selected.extraction_status,
                    extracted_at=selected.extracted_at,
                    span_count=span_count,
                )
            )
            continue

        fallback_applies = (
            normalized_fallback_text
            and normalized_fallback_type is not None
            and normalized_fallback_type == source_type
        )
        if fallback_applies:
            composed_sources.append(
                ComposedSourceDocument(
                    source_type=source_type,
                    source_origin="fallback_extract",
                    coverage_status="partial",
                    text=normalized_fallback_text,
                    canonical_document_id=None,
                    revision_id=None,
                    revision_number=None,
                    extraction_status=None,
                    extracted_at=None,
                    span_count=0,
                )
            )
            continue

        composed_sources.append(
            ComposedSourceDocument(
                source_type=source_type,
                source_origin="missing",
                coverage_status="missing",
                text="",
                canonical_document_id=None,
                revision_id=None,
                revision_number=None,
                extraction_status=None,
                extracted_at=None,
                span_count=0,
            )
        )

    source_coverage = _build_source_coverage(sources=tuple(composed_sources))
    composed_text = _compose_text_payload(sources=tuple(composed_sources), fallback_text=normalized_fallback_text)

    return SummarizeComposeInput(
        meeting_id=meeting_id,
        source_order=EXPECTED_SOURCE_TYPES,
        sources=tuple(composed_sources),
        composed_text=composed_text,
        source_coverage=source_coverage,
    )


def _normalize_source_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in EXPECTED_SOURCE_TYPES:
        return normalized
    return None


def _select_preferred_document(
    *,
    documents: tuple[CanonicalDocumentRecord, ...],
    source_type: str,
) -> CanonicalDocumentRecord | None:
    candidates = [item for item in documents if item.document_kind == source_type]
    if not candidates:
        return None

    ordered = sorted(candidates, key=lambda item: item.id)
    ordered = sorted(ordered, key=lambda item: item.extracted_at or "", reverse=True)
    ordered = sorted(ordered, key=lambda item: item.revision_number, reverse=True)
    ordered = sorted(ordered, key=lambda item: item.is_active_revision, reverse=True)
    return ordered[0]


def _compose_document_text(
    *,
    connection: sqlite3.Connection,
    canonical_document_id: str,
) -> tuple[str, int]:
    rows = connection.execute(
        """
        SELECT span_text
        FROM canonical_document_spans
        WHERE canonical_document_id = ?
          AND span_text IS NOT NULL
          AND TRIM(span_text) != ''
        ORDER BY
            stable_section_path ASC,
            page_number IS NULL,
            page_number ASC,
            line_index IS NULL,
            line_index ASC,
            start_char_offset IS NULL,
            start_char_offset ASC,
            end_char_offset IS NULL,
            end_char_offset ASC,
            locator_fingerprint ASC,
            id ASC
        """,
        (canonical_document_id,),
    ).fetchall()

    parts: list[str] = []
    for row in rows:
        raw = row[0]
        if raw is None:
            continue
        normalized = " ".join(str(raw).split())
        if normalized:
            parts.append(normalized)

    return " ".join(parts), len(parts)


def _build_source_coverage(*, sources: tuple[ComposedSourceDocument, ...]) -> SourceCoverageSummary:
    statuses = {item.source_type: item.coverage_status for item in sources}

    canonical_source_types = tuple(item.source_type for item in sources if item.source_origin == "canonical")
    fallback_source_types = tuple(item.source_type for item in sources if item.source_origin == "fallback_extract")
    partial_source_types = tuple(item.source_type for item in sources if item.coverage_status == "partial")
    missing_source_types = tuple(item.source_type for item in sources if item.coverage_status == "missing")
    available_source_types = tuple(item.source_type for item in sources if item.coverage_status != "missing")
    coverage_ratio = round(len(available_source_types) / len(EXPECTED_SOURCE_TYPES), 4)

    checksum_payload = {
        "source_order": list(EXPECTED_SOURCE_TYPES),
        "statuses": statuses,
        "documents": [
            {
                "source_type": source.source_type,
                "source_origin": source.source_origin,
                "coverage_status": source.coverage_status,
                "canonical_document_id": source.canonical_document_id,
                "revision_id": source.revision_id,
                "revision_number": source.revision_number,
                "text_char_count": len(source.text),
            }
            for source in sources
        ],
    }
    checksum = "sha256:" + hashlib.sha256(
        json.dumps(checksum_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()

    return SourceCoverageSummary(
        source_order=EXPECTED_SOURCE_TYPES,
        statuses=statuses,
        canonical_source_types=canonical_source_types,
        fallback_source_types=fallback_source_types,
        partial_source_types=partial_source_types,
        missing_source_types=missing_source_types,
        available_source_types=available_source_types,
        coverage_ratio=coverage_ratio,
        coverage_checksum=checksum,
    )


def _compose_text_payload(*, sources: tuple[ComposedSourceDocument, ...], fallback_text: str) -> str:
    chunks: list[str] = []
    for source in sources:
        if not source.text:
            continue
        chunks.append(f"[{source.source_type}] {source.text}")

    composed = "\n\n".join(chunks).strip()
    if composed:
        return composed
    if fallback_text:
        return fallback_text
    return "No source text available."
