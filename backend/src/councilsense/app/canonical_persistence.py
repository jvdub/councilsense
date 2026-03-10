from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from councilsense.db import (
    CanonicalDocumentArtifactRepository,
    CanonicalDocumentRepository,
    DocumentKind,
    ExtractionStatus,
)


_SPAN_PARSER_NAME = "claim-evidence-pointer-normalizer"
_SPAN_PARSER_VERSION = "st024-v1"
_NORMALIZER_NAME = "local-runtime-extract"
_NORMALIZER_VERSION = "st024-v1"


@dataclass(frozen=True)
class EvidenceSpanInput:
    stable_section_path: str | None
    line_index: int | None
    start_char_offset: int | None
    end_char_offset: int | None
    source_chunk_id: str | None
    span_text: str | None


@dataclass(frozen=True)
class CanonicalPipelineWriteResult:
    canonical_document_id: str
    document_kind: DocumentKind
    revision_id: str
    revision_number: int
    raw_artifact_id: str
    normalized_artifact_id: str
    span_count: int


@dataclass(frozen=True)
class BackfillMeetingAudit:
    meeting_id: str
    publication_id: str | None
    status: Literal["would_write", "written", "already_current", "skipped_no_publication"]
    documents_delta: int
    artifacts_delta: int
    spans_delta: int

    def to_payload(self) -> dict[str, object]:
        return {
            "meeting_id": self.meeting_id,
            "publication_id": self.publication_id,
            "status": self.status,
            "documents_delta": self.documents_delta,
            "artifacts_delta": self.artifacts_delta,
            "spans_delta": self.spans_delta,
        }


@dataclass(frozen=True)
class PilotCanonicalBackfillResult:
    city_id: str
    dry_run: bool
    start_date: str | None
    end_date: str | None
    scanned_meetings: int
    meetings_with_publications: int
    meetings_written: int
    audits: tuple[BackfillMeetingAudit, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "city_id": self.city_id,
            "dry_run": self.dry_run,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "scanned_meetings": self.scanned_meetings,
            "meetings_with_publications": self.meetings_with_publications,
            "meetings_written": self.meetings_written,
            "audits": [item.to_payload() for item in self.audits],
        }


def persist_pipeline_canonical_records(
    connection: sqlite3.Connection,
    *,
    meeting_id: str,
    source_id: str | None,
    source_url: str | None,
    source_type_override: str | None = None,
    parser_name_override: str | None = None,
    parser_version_override: str | None = None,
    extracted_text: str,
    extraction_status: ExtractionStatus,
    extraction_confidence: float | None,
    artifact_storage_uri: str | None,
    evidence_spans: tuple[EvidenceSpanInput, ...],
    extracted_at: str | None = None,
) -> CanonicalPipelineWriteResult:
    document_repository = CanonicalDocumentRepository(connection)
    artifact_repository = CanonicalDocumentArtifactRepository(connection)

    source_type, resolved_source_url, parser_name, parser_version = _resolve_source_metadata(
        connection=connection,
        source_id=source_id,
        source_url=source_url,
        source_type_override=source_type_override,
        parser_name_override=parser_name_override,
        parser_version_override=parser_version_override,
    )
    document_kind = _map_source_type_to_document_kind(source_type)

    raw_bytes = _read_artifact_bytes(artifact_storage_uri)
    normalized_text = " ".join(extracted_text.split())
    raw_checksum = _sha256_prefixed(raw_bytes if raw_bytes is not None else normalized_text.encode("utf-8"))
    normalized_checksum = _sha256_prefixed(normalized_text.encode("utf-8"))

    existing_documents = tuple(
        item
        for item in document_repository.list_documents_for_meeting(meeting_id=meeting_id)
        if item.document_kind == document_kind
    )
    existing_revision = next((item for item in existing_documents if item.source_checksum == raw_checksum), None)

    if existing_revision is not None:
        revision_number = existing_revision.revision_number
        revision_id = existing_revision.revision_id
        canonical_document_id = existing_revision.id
    else:
        max_revision = max((item.revision_number for item in existing_documents), default=0)
        revision_number = max_revision + 1
        revision_id = f"checksum:{raw_checksum}"
        canonical_document_id = f"canon-{meeting_id}-{document_kind}-r{revision_number}"

    authority_level = "authoritative" if document_kind == "minutes" else "supplemental"
    authority_note = (
        "minutes are authoritative for outcomes"
        if document_kind == "minutes"
        else "supplemental source for context and evidence"
    )
    document = document_repository.upsert_document_revision(
        canonical_document_id=canonical_document_id,
        meeting_id=meeting_id,
        document_kind=document_kind,
        revision_id=revision_id,
        revision_number=revision_number,
        is_active_revision=True,
        authority_level=authority_level,
        authority_source="minutes_policy_v1",
        authority_note=authority_note,
        source_document_url=resolved_source_url,
        source_checksum=raw_checksum,
        parser_name=parser_name,
        parser_version=parser_version,
        extraction_status=extraction_status,
        extraction_confidence=extraction_confidence,
        extracted_at=extracted_at or _now_iso_utc(),
    )

    raw_artifact = artifact_repository.upsert_artifact(
        artifact_id=f"artifact-raw-{document.id}-{_digest_suffix(raw_checksum)}",
        canonical_document_id=document.id,
        artifact_kind="raw",
        content_checksum=raw_checksum,
        storage_uri=artifact_storage_uri,
        lineage_parent_artifact_id=None,
        normalizer_name=None,
        normalizer_version=None,
    )
    normalized_artifact = artifact_repository.upsert_artifact(
        artifact_id=f"artifact-normalized-{document.id}-{_digest_suffix(normalized_checksum)}",
        canonical_document_id=document.id,
        artifact_kind="normalized",
        content_checksum=normalized_checksum,
        storage_uri=None,
        lineage_parent_artifact_id=raw_artifact.id,
        normalizer_name=_NORMALIZER_NAME,
        normalizer_version=_NORMALIZER_VERSION,
    )

    span_inputs = evidence_spans
    if not span_inputs:
        span_inputs = (
            EvidenceSpanInput(
                stable_section_path=f"{document_kind}/content/1",
                line_index=0,
                start_char_offset=None,
                end_char_offset=None,
                source_chunk_id="claim-1-evidence-1",
                span_text=(normalized_text[:300] if normalized_text else "No extracted text available."),
            ),
        )

    for index, span in enumerate(span_inputs, start=1):
        stable_path = _normalize_section_path(span.stable_section_path, fallback_kind=document_kind, index=index)
        checksum_value = _sha256_prefixed(span.span_text.encode("utf-8")) if span.span_text else None
        document_repository.upsert_document_span(
            canonical_document_span_id=(
                f"span-{document.id}-{_digest_suffix(stable_path)}-{index}"
            ),
            canonical_document_id=document.id,
            artifact_id=normalized_artifact.id,
            stable_section_path=stable_path,
            page_number=None,
            line_index=span.line_index,
            start_char_offset=span.start_char_offset,
            end_char_offset=span.end_char_offset,
            parser_name=_SPAN_PARSER_NAME,
            parser_version=_SPAN_PARSER_VERSION,
            source_chunk_id=span.source_chunk_id,
            span_text=span.span_text,
            span_text_checksum=checksum_value,
        )

    return CanonicalPipelineWriteResult(
        canonical_document_id=document.id,
        document_kind=document.document_kind,
        revision_id=document.revision_id,
        revision_number=document.revision_number,
        raw_artifact_id=raw_artifact.id,
        normalized_artifact_id=normalized_artifact.id,
        span_count=len(span_inputs),
    )


def run_pilot_canonical_backfill(
    connection: sqlite3.Connection,
    *,
    city_id: str,
    start_date: str | None,
    end_date: str | None,
    limit: int,
    dry_run: bool,
) -> PilotCanonicalBackfillResult:
    meeting_rows = _list_meeting_rows(
        connection=connection,
        city_id=city_id,
        start_date=start_date,
        end_date=end_date,
        limit=max(limit, 1),
    )

    audits: list[BackfillMeetingAudit] = []
    meetings_with_publications = 0
    meetings_written = 0

    for row in meeting_rows:
        meeting_id = str(row[0])
        title = str(row[1])

        publication = connection.execute(
            """
            SELECT id, summary_text
            FROM summary_publications
            WHERE meeting_id = ?
            ORDER BY version_no DESC, published_at DESC, id DESC
            LIMIT 1
            """,
            (meeting_id,),
        ).fetchone()
        if publication is None:
            audits.append(
                BackfillMeetingAudit(
                    meeting_id=meeting_id,
                    publication_id=None,
                    status="skipped_no_publication",
                    documents_delta=0,
                    artifacts_delta=0,
                    spans_delta=0,
                )
            )
            continue

        meetings_with_publications += 1
        publication_id = str(publication[0])
        summary_text = str(publication[1])
        evidence_rows = connection.execute(
            """
            SELECT
                cep.id,
                cep.section_ref,
                cep.char_start,
                cep.char_end,
                cep.excerpt
            FROM publication_claims pc
            INNER JOIN claim_evidence_pointers cep ON cep.claim_id = pc.id
            WHERE pc.publication_id = ?
            ORDER BY pc.claim_order ASC, cep.id ASC
            """,
            (publication_id,),
        ).fetchall()
        evidence_spans = tuple(
            EvidenceSpanInput(
                stable_section_path=str(item[1]) if item[1] is not None else None,
                line_index=None,
                start_char_offset=int(item[2]) if item[2] is not None else None,
                end_char_offset=int(item[3]) if item[3] is not None else None,
                source_chunk_id=str(item[0]),
                span_text=str(item[4]) if item[4] is not None else None,
            )
            for item in evidence_rows
        )

        before = _meeting_lineage_counts(connection=connection, meeting_id=meeting_id)
        extracted_text = _compose_backfill_text(
            title=title,
            summary_text=summary_text,
            spans=evidence_spans,
        )

        if dry_run:
            status: Literal["would_write", "written", "already_current", "skipped_no_publication"] = "would_write"
            audits.append(
                BackfillMeetingAudit(
                    meeting_id=meeting_id,
                    publication_id=publication_id,
                    status=status,
                    documents_delta=0,
                    artifacts_delta=0,
                    spans_delta=0,
                )
            )
            continue

        persist_pipeline_canonical_records(
            connection,
            meeting_id=meeting_id,
            source_id=None,
            source_url=None,
            extracted_text=extracted_text,
            extraction_status=("processed" if evidence_spans else "limited_confidence"),
            extraction_confidence=(0.75 if evidence_spans else 0.55),
            artifact_storage_uri=None,
            evidence_spans=evidence_spans,
        )

        after = _meeting_lineage_counts(connection=connection, meeting_id=meeting_id)
        documents_delta = after[0] - before[0]
        artifacts_delta = after[1] - before[1]
        spans_delta = after[2] - before[2]
        status = "written" if (documents_delta + artifacts_delta + spans_delta) > 0 else "already_current"
        if status == "written":
            meetings_written += 1

        audits.append(
            BackfillMeetingAudit(
                meeting_id=meeting_id,
                publication_id=publication_id,
                status=status,
                documents_delta=documents_delta,
                artifacts_delta=artifacts_delta,
                spans_delta=spans_delta,
            )
        )

    return PilotCanonicalBackfillResult(
        city_id=city_id,
        dry_run=dry_run,
        start_date=start_date,
        end_date=end_date,
        scanned_meetings=len(meeting_rows),
        meetings_with_publications=meetings_with_publications,
        meetings_written=meetings_written,
        audits=tuple(audits),
    )


def _compose_backfill_text(*, title: str, summary_text: str, spans: tuple[EvidenceSpanInput, ...]) -> str:
    excerpts = [item.span_text for item in spans if item.span_text]
    if excerpts:
        return " ".join(excerpts)
    if summary_text.strip():
        return summary_text.strip()
    return title.strip() or "Backfill source unavailable"


def _meeting_lineage_counts(*, connection: sqlite3.Connection, meeting_id: str) -> tuple[int, int, int]:
    documents = connection.execute(
        "SELECT COUNT(*) FROM canonical_documents WHERE meeting_id = ?",
        (meeting_id,),
    ).fetchone()
    artifacts = connection.execute(
        """
        SELECT COUNT(*)
        FROM canonical_document_artifacts a
        INNER JOIN canonical_documents d ON d.id = a.canonical_document_id
        WHERE d.meeting_id = ?
        """,
        (meeting_id,),
    ).fetchone()
    spans = connection.execute(
        """
        SELECT COUNT(*)
        FROM canonical_document_spans s
        INNER JOIN canonical_documents d ON d.id = s.canonical_document_id
        WHERE d.meeting_id = ?
        """,
        (meeting_id,),
    ).fetchone()
    return (int(documents[0]), int(artifacts[0]), int(spans[0]))


def _list_meeting_rows(
    *,
    connection: sqlite3.Connection,
    city_id: str,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> tuple[tuple[object, ...], ...]:
    clauses = ["city_id = ?"]
    params: list[object] = [city_id]

    if start_date is not None:
        clauses.append("date(created_at) >= date(?)")
        params.append(start_date)
    if end_date is not None:
        clauses.append("date(created_at) <= date(?)")
        params.append(end_date)

    where_sql = " AND ".join(clauses)
    query = (
        "SELECT id, title FROM meetings "
        f"WHERE {where_sql} "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT ?"
    )
    params.append(limit)
    rows = connection.execute(query, tuple(params)).fetchall()
    return tuple(rows)


def _resolve_source_metadata(
    *,
    connection: sqlite3.Connection,
    source_id: str | None,
    source_url: str | None,
    source_type_override: str | None,
    parser_name_override: str | None,
    parser_version_override: str | None,
) -> tuple[str, str | None, str, str]:
    normalized_override = _normalize_source_type(source_type_override)
    resolved_parser_name = (parser_name_override or "local-runtime").strip() or "local-runtime"
    resolved_parser_version = (parser_version_override or "st024-v1").strip() or "st024-v1"

    if source_id is None:
        return (
            normalized_override or "minutes",
            source_url,
            resolved_parser_name,
            resolved_parser_version,
        )

    row = connection.execute(
        """
        SELECT source_type, source_url, parser_name, parser_version
        FROM city_sources
        WHERE id = ?
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()
    if row is None:
        return (
            normalized_override or "minutes",
            source_url,
            resolved_parser_name,
            resolved_parser_version,
        )
    return (
        normalized_override or _normalize_source_type(str(row[0])) or "minutes",
        source_url if source_url is not None else (str(row[1]) if row[1] is not None else None),
        resolved_parser_name if parser_name_override is not None else (str(row[2]) if row[2] is not None else resolved_parser_name),
        resolved_parser_version if parser_version_override is not None else (str(row[3]) if row[3] is not None else resolved_parser_version),
    )


def _normalize_source_type(source_type: str | None) -> str | None:
    if source_type is None:
        return None
    normalized = source_type.strip().lower()
    if normalized == "minutes":
        return "minutes"
    if normalized == "agenda":
        return "agenda"
    if normalized == "packet":
        return "packet"
    return None


def _map_source_type_to_document_kind(source_type: str) -> DocumentKind:
    normalized = source_type.strip().lower()
    if normalized == "minutes":
        return "minutes"
    if normalized == "agenda":
        return "agenda"
    if normalized == "packet":
        return "packet"
    return "minutes"


def _read_artifact_bytes(storage_uri: str | None) -> bytes | None:
    if storage_uri is None:
        return None
    try:
        path = Path(storage_uri)
        if path.exists() and path.is_file():
            return path.read_bytes()
    except OSError:
        return None
    return None


def _sha256_prefixed(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _digest_suffix(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:16]


def _normalize_section_path(value: str | None, *, fallback_kind: DocumentKind, index: int) -> str:
    if value is None:
        return f"{fallback_kind}/content/{index}"
    normalized = value.strip().replace(".", "/")
    normalized = "/".join(part for part in normalized.split("/") if part)
    if not normalized:
        return f"{fallback_kind}/content/{index}"
    return normalized


def _now_iso_utc() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
