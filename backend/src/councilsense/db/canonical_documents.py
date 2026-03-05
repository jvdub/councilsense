from __future__ import annotations

import sqlite3
from dataclasses import dataclass
import hashlib
from typing import Any
from typing import cast
from typing import Literal


DocumentKind = Literal["minutes", "agenda", "packet"]
AuthorityLevel = Literal["authoritative", "supplemental"]
ExtractionStatus = Literal["pending", "processed", "failed", "limited_confidence"]


@dataclass(frozen=True)
class CanonicalDocumentRecord:
    id: str
    meeting_id: str
    document_kind: DocumentKind
    revision_id: str
    revision_number: int
    is_active_revision: bool
    authority_level: AuthorityLevel
    authority_source: str
    authority_note: str | None
    source_document_url: str | None
    source_checksum: str | None
    parser_name: str
    parser_version: str
    extraction_status: ExtractionStatus
    extraction_confidence: float | None
    extracted_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CanonicalDocumentSpanRecord:
    id: str
    canonical_document_id: str
    artifact_id: str | None
    stable_section_path: str
    page_number: int | None
    line_index: int | None
    start_char_offset: int | None
    end_char_offset: int | None
    locator_fingerprint: str
    parser_name: str
    parser_version: str
    source_chunk_id: str | None
    span_text: str | None
    span_text_checksum: str | None
    created_at: str
    updated_at: str


class CanonicalDocumentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert_document_revision(
        self,
        *,
        canonical_document_id: str,
        meeting_id: str,
        document_kind: DocumentKind,
        revision_id: str,
        revision_number: int,
        is_active_revision: bool,
        authority_level: AuthorityLevel,
        authority_source: str,
        authority_note: str | None,
        source_document_url: str | None,
        source_checksum: str | None,
        parser_name: str,
        parser_version: str,
        extraction_status: ExtractionStatus,
        extraction_confidence: float | None,
        extracted_at: str | None,
    ) -> CanonicalDocumentRecord:
        with self._connection:
            if is_active_revision:
                self._connection.execute(
                    """
                    UPDATE canonical_documents
                    SET
                        is_active_revision = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE meeting_id = ?
                      AND document_kind = ?
                      AND is_active_revision = 1
                    """,
                    (meeting_id, document_kind),
                )

            self._connection.execute(
                """
                INSERT INTO canonical_documents (
                    id,
                    meeting_id,
                    document_kind,
                    revision_id,
                    revision_number,
                    is_active_revision,
                    authority_level,
                    authority_source,
                    authority_note,
                    source_document_url,
                    source_checksum,
                    parser_name,
                    parser_version,
                    extraction_status,
                    extraction_confidence,
                    extracted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (meeting_id, document_kind, revision_id)
                DO UPDATE SET
                    revision_number = excluded.revision_number,
                    is_active_revision = excluded.is_active_revision,
                    authority_level = excluded.authority_level,
                    authority_source = excluded.authority_source,
                    authority_note = excluded.authority_note,
                    source_document_url = excluded.source_document_url,
                    source_checksum = excluded.source_checksum,
                    parser_name = excluded.parser_name,
                    parser_version = excluded.parser_version,
                    extraction_status = excluded.extraction_status,
                    extraction_confidence = excluded.extraction_confidence,
                    extracted_at = excluded.extracted_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    canonical_document_id,
                    meeting_id,
                    document_kind,
                    revision_id,
                    revision_number,
                    1 if is_active_revision else 0,
                    authority_level,
                    authority_source,
                    authority_note,
                    source_document_url,
                    source_checksum,
                    parser_name,
                    parser_version,
                    extraction_status,
                    extraction_confidence,
                    extracted_at,
                ),
            )

        row = self._connection.execute(
            """
            SELECT
                id,
                meeting_id,
                document_kind,
                revision_id,
                revision_number,
                is_active_revision,
                authority_level,
                authority_source,
                authority_note,
                source_document_url,
                source_checksum,
                parser_name,
                parser_version,
                extraction_status,
                extraction_confidence,
                extracted_at,
                created_at,
                updated_at
            FROM canonical_documents
            WHERE meeting_id = ?
              AND document_kind = ?
              AND revision_id = ?
            """,
            (meeting_id, document_kind, revision_id),
        ).fetchone()
        assert row is not None
        return _to_record(row)

    def get_active_document(
        self,
        *,
        meeting_id: str,
        document_kind: DocumentKind,
    ) -> CanonicalDocumentRecord | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                meeting_id,
                document_kind,
                revision_id,
                revision_number,
                is_active_revision,
                authority_level,
                authority_source,
                authority_note,
                source_document_url,
                source_checksum,
                parser_name,
                parser_version,
                extraction_status,
                extraction_confidence,
                extracted_at,
                created_at,
                updated_at
            FROM canonical_documents
            WHERE meeting_id = ?
              AND document_kind = ?
              AND is_active_revision = 1
            ORDER BY revision_number DESC, updated_at DESC, id DESC
            LIMIT 1
            """,
            (meeting_id, document_kind),
        ).fetchone()
        if row is None:
            return None
        return _to_record(row)

    def list_documents_for_meeting(self, *, meeting_id: str) -> tuple[CanonicalDocumentRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                meeting_id,
                document_kind,
                revision_id,
                revision_number,
                is_active_revision,
                authority_level,
                authority_source,
                authority_note,
                source_document_url,
                source_checksum,
                parser_name,
                parser_version,
                extraction_status,
                extraction_confidence,
                extracted_at,
                created_at,
                updated_at
            FROM canonical_documents
            WHERE meeting_id = ?
            ORDER BY document_kind ASC, revision_number DESC, id DESC
            """,
            (meeting_id,),
        ).fetchall()
        return tuple(_to_record(row) for row in rows)

    def upsert_document_span(
        self,
        *,
        canonical_document_span_id: str,
        canonical_document_id: str,
        artifact_id: str | None,
        stable_section_path: str,
        page_number: int | None,
        line_index: int | None,
        start_char_offset: int | None,
        end_char_offset: int | None,
        parser_name: str,
        parser_version: str,
        source_chunk_id: str | None,
        span_text: str | None,
        span_text_checksum: str | None,
    ) -> CanonicalDocumentSpanRecord:
        canonical_path = _canonicalize_section_path(stable_section_path)
        artifact_scope = artifact_id or ""
        locator_fingerprint = _build_locator_fingerprint(
            stable_section_path=canonical_path,
            page_number=page_number,
            line_index=line_index,
            start_char_offset=start_char_offset,
            end_char_offset=end_char_offset,
        )

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO canonical_document_spans (
                    id,
                    canonical_document_id,
                    artifact_id,
                    artifact_scope,
                    stable_section_path,
                    page_number,
                    line_index,
                    start_char_offset,
                    end_char_offset,
                    locator_fingerprint,
                    parser_name,
                    parser_version,
                    source_chunk_id,
                    span_text,
                    span_text_checksum
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    canonical_document_id,
                    artifact_scope,
                    locator_fingerprint,
                    parser_name,
                    parser_version
                )
                DO UPDATE SET
                    artifact_id = excluded.artifact_id,
                    stable_section_path = excluded.stable_section_path,
                    page_number = excluded.page_number,
                    line_index = excluded.line_index,
                    start_char_offset = excluded.start_char_offset,
                    end_char_offset = excluded.end_char_offset,
                    source_chunk_id = excluded.source_chunk_id,
                    span_text = excluded.span_text,
                    span_text_checksum = excluded.span_text_checksum,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    canonical_document_span_id,
                    canonical_document_id,
                    artifact_id,
                    artifact_scope,
                    canonical_path,
                    page_number,
                    line_index,
                    start_char_offset,
                    end_char_offset,
                    locator_fingerprint,
                    parser_name,
                    parser_version,
                    source_chunk_id,
                    span_text,
                    span_text_checksum,
                ),
            )

        row = self._connection.execute(
            """
            SELECT
                id,
                canonical_document_id,
                artifact_id,
                stable_section_path,
                page_number,
                line_index,
                start_char_offset,
                end_char_offset,
                locator_fingerprint,
                parser_name,
                parser_version,
                source_chunk_id,
                span_text,
                span_text_checksum,
                created_at,
                updated_at
            FROM canonical_document_spans
            WHERE canonical_document_id = ?
              AND artifact_scope = ?
              AND locator_fingerprint = ?
              AND parser_name = ?
              AND parser_version = ?
            LIMIT 1
            """,
            (
                canonical_document_id,
                artifact_scope,
                locator_fingerprint,
                parser_name,
                parser_version,
            ),
        ).fetchone()
        assert row is not None
        return _to_span_record(row)

    def list_document_spans(
        self,
        *,
        canonical_document_id: str,
        artifact_id: str | None = None,
    ) -> tuple[CanonicalDocumentSpanRecord, ...]:
        artifact_scope = artifact_id or ""
        rows = self._connection.execute(
            """
            SELECT
                id,
                canonical_document_id,
                artifact_id,
                stable_section_path,
                page_number,
                line_index,
                start_char_offset,
                end_char_offset,
                locator_fingerprint,
                parser_name,
                parser_version,
                source_chunk_id,
                span_text,
                span_text_checksum,
                created_at,
                updated_at
            FROM canonical_document_spans
            WHERE canonical_document_id = ?
              AND artifact_scope = ?
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
            (canonical_document_id, artifact_scope),
        ).fetchall()
        return tuple(_to_span_record(row) for row in rows)


def _to_record(row: sqlite3.Row | tuple[Any, ...]) -> CanonicalDocumentRecord:
    document_kind = cast(DocumentKind, str(row[2]))
    authority_level = cast(AuthorityLevel, str(row[6]))
    extraction_status = cast(ExtractionStatus, str(row[13]))
    return CanonicalDocumentRecord(
        id=str(row[0]),
        meeting_id=str(row[1]),
        document_kind=document_kind,
        revision_id=str(row[3]),
        revision_number=int(row[4]),
        is_active_revision=bool(row[5]),
        authority_level=authority_level,
        authority_source=str(row[7]),
        authority_note=str(row[8]) if row[8] is not None else None,
        source_document_url=str(row[9]) if row[9] is not None else None,
        source_checksum=str(row[10]) if row[10] is not None else None,
        parser_name=str(row[11]),
        parser_version=str(row[12]),
        extraction_status=extraction_status,
        extraction_confidence=float(row[14]) if row[14] is not None else None,
        extracted_at=str(row[15]) if row[15] is not None else None,
        created_at=str(row[16]),
        updated_at=str(row[17]),
    )


def _to_span_record(row: sqlite3.Row | tuple[Any, ...]) -> CanonicalDocumentSpanRecord:
    return CanonicalDocumentSpanRecord(
        id=str(row[0]),
        canonical_document_id=str(row[1]),
        artifact_id=str(row[2]) if row[2] is not None else None,
        stable_section_path=str(row[3]),
        page_number=int(row[4]) if row[4] is not None else None,
        line_index=int(row[5]) if row[5] is not None else None,
        start_char_offset=int(row[6]) if row[6] is not None else None,
        end_char_offset=int(row[7]) if row[7] is not None else None,
        locator_fingerprint=str(row[8]),
        parser_name=str(row[9]),
        parser_version=str(row[10]),
        source_chunk_id=str(row[11]) if row[11] is not None else None,
        span_text=str(row[12]) if row[12] is not None else None,
        span_text_checksum=str(row[13]) if row[13] is not None else None,
        created_at=str(row[14]),
        updated_at=str(row[15]),
    )


def _canonicalize_section_path(section_path: str) -> str:
    normalized = section_path.strip().replace("\\", "/")
    parts = [part.strip() for part in normalized.split("/") if part.strip()]
    canonical = "/".join(parts)
    if not canonical:
        raise ValueError("stable_section_path must contain at least one non-empty segment")
    return canonical


def _build_locator_fingerprint(
    *,
    stable_section_path: str,
    page_number: int | None,
    line_index: int | None,
    start_char_offset: int | None,
    end_char_offset: int | None,
) -> str:
    locator_payload = "|".join(
        (
            stable_section_path,
            str(page_number) if page_number is not None else "",
            str(line_index) if line_index is not None else "",
            str(start_char_offset) if start_char_offset is not None else "",
            str(end_char_offset) if end_char_offset is not None else "",
        )
    )
    return hashlib.sha256(locator_payload.encode("utf-8")).hexdigest()
