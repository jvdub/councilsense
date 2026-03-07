from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal


DEFAULT_SUMMARY_CALIBRATION_POLICY_VERSION = "st015-calibration-policy-v1-default"


PublicationStatus = Literal["processed", "limited_confidence"]
ConfidenceLabel = Literal["high", "medium", "low", "limited_confidence"]


@dataclass(frozen=True)
class SummaryPublicationRecord:
    id: str
    meeting_id: str
    processing_run_id: str | None
    publish_stage_outcome_id: str | None
    version_no: int
    publication_status: PublicationStatus
    confidence_label: ConfidenceLabel
    calibration_policy_version: str
    summary_text: str
    key_decisions_json: str
    key_actions_json: str
    notable_topics_json: str
    published_at: str


@dataclass(frozen=True)
class PublicationClaimRecord:
    id: str
    publication_id: str
    claim_order: int
    claim_text: str


@dataclass(frozen=True)
class ClaimEvidencePointerRecord:
    id: str
    claim_id: str
    artifact_id: str
    section_ref: str | None
    char_start: int | None
    char_end: int | None
    excerpt: str
    document_id: str | None
    span_id: str | None
    document_kind: str | None
    section_path: str | None
    precision: str | None
    confidence: str | None


class MeetingSummaryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def create_publication(
        self,
        *,
        publication_id: str,
        meeting_id: str,
        processing_run_id: str | None,
        publish_stage_outcome_id: str | None,
        version_no: int,
        publication_status: PublicationStatus,
        confidence_label: ConfidenceLabel,
        summary_text: str,
        key_decisions_json: str,
        key_actions_json: str,
        notable_topics_json: str,
        published_at: str | None,
        calibration_policy_version: str = DEFAULT_SUMMARY_CALIBRATION_POLICY_VERSION,
    ) -> SummaryPublicationRecord:
        with self._connection:
            return self.create_publication_in_transaction(
                publication_id=publication_id,
                meeting_id=meeting_id,
                processing_run_id=processing_run_id,
                publish_stage_outcome_id=publish_stage_outcome_id,
                version_no=version_no,
                publication_status=publication_status,
                confidence_label=confidence_label,
                calibration_policy_version=calibration_policy_version,
                summary_text=summary_text,
                key_decisions_json=key_decisions_json,
                key_actions_json=key_actions_json,
                notable_topics_json=notable_topics_json,
                published_at=published_at,
            )

    def create_publication_in_transaction(
        self,
        *,
        publication_id: str,
        meeting_id: str,
        processing_run_id: str | None,
        publish_stage_outcome_id: str | None,
        version_no: int,
        publication_status: PublicationStatus,
        confidence_label: ConfidenceLabel,
        summary_text: str,
        key_decisions_json: str,
        key_actions_json: str,
        notable_topics_json: str,
        published_at: str | None,
        calibration_policy_version: str = DEFAULT_SUMMARY_CALIBRATION_POLICY_VERSION,
    ) -> SummaryPublicationRecord:
        self._connection.execute(
            """
            INSERT INTO summary_publications (
                id,
                meeting_id,
                processing_run_id,
                publish_stage_outcome_id,
                version_no,
                publication_status,
                confidence_label,
                calibration_policy_version,
                summary_text,
                key_decisions_json,
                key_actions_json,
                notable_topics_json,
                published_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
            """,
            (
                publication_id,
                meeting_id,
                processing_run_id,
                publish_stage_outcome_id,
                version_no,
                publication_status,
                confidence_label,
                calibration_policy_version,
                summary_text,
                key_decisions_json,
                key_actions_json,
                notable_topics_json,
                published_at,
            ),
        )

        row = self._connection.execute(
            """
            SELECT
                id,
                meeting_id,
                processing_run_id,
                publish_stage_outcome_id,
                version_no,
                publication_status,
                confidence_label,
                calibration_policy_version,
                summary_text,
                key_decisions_json,
                key_actions_json,
                notable_topics_json,
                published_at
            FROM summary_publications
            WHERE id = ?
            """,
            (publication_id,),
        ).fetchone()
        assert row is not None
        return SummaryPublicationRecord(
            id=str(row[0]),
            meeting_id=str(row[1]),
            processing_run_id=str(row[2]) if row[2] is not None else None,
            publish_stage_outcome_id=str(row[3]) if row[3] is not None else None,
            version_no=int(row[4]),
            publication_status=str(row[5]),
            confidence_label=str(row[6]),
            calibration_policy_version=str(row[7]),
            summary_text=str(row[8]),
            key_decisions_json=str(row[9]),
            key_actions_json=str(row[10]),
            notable_topics_json=str(row[11]),
            published_at=str(row[12]),
        )

    def add_claim(
        self,
        *,
        claim_id: str,
        publication_id: str,
        claim_order: int,
        claim_text: str,
    ) -> PublicationClaimRecord:
        with self._connection:
            return self.add_claim_in_transaction(
                claim_id=claim_id,
                publication_id=publication_id,
                claim_order=claim_order,
                claim_text=claim_text,
            )

    def add_claim_in_transaction(
        self,
        *,
        claim_id: str,
        publication_id: str,
        claim_order: int,
        claim_text: str,
    ) -> PublicationClaimRecord:
        self._connection.execute(
            """
            INSERT INTO publication_claims (
                id,
                publication_id,
                claim_order,
                claim_text
            )
            VALUES (?, ?, ?, ?)
            """,
            (claim_id, publication_id, claim_order, claim_text),
        )

        row = self._connection.execute(
            """
            SELECT id, publication_id, claim_order, claim_text
            FROM publication_claims
            WHERE id = ?
            """,
            (claim_id,),
        ).fetchone()
        assert row is not None
        return PublicationClaimRecord(
            id=str(row[0]),
            publication_id=str(row[1]),
            claim_order=int(row[2]),
            claim_text=str(row[3]),
        )

    def add_claim_evidence_pointer(
        self,
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
    ) -> ClaimEvidencePointerRecord:
        with self._connection:
            return self.add_claim_evidence_pointer_in_transaction(
                pointer_id=pointer_id,
                claim_id=claim_id,
                artifact_id=artifact_id,
                section_ref=section_ref,
                char_start=char_start,
                char_end=char_end,
                excerpt=excerpt,
                document_id=document_id,
                span_id=span_id,
                document_kind=document_kind,
                section_path=section_path,
                precision=precision,
                confidence=confidence,
            )

    def add_claim_evidence_pointer_in_transaction(
        self,
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
    ) -> ClaimEvidencePointerRecord:
        self._connection.execute(
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

        row = self._connection.execute(
            """
            SELECT
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
            FROM claim_evidence_pointers
            WHERE id = ?
            """,
            (pointer_id,),
        ).fetchone()
        assert row is not None
        return ClaimEvidencePointerRecord(
            id=str(row[0]),
            claim_id=str(row[1]),
            artifact_id=str(row[2]),
            section_ref=str(row[3]) if row[3] is not None else None,
            char_start=int(row[4]) if row[4] is not None else None,
            char_end=int(row[5]) if row[5] is not None else None,
            excerpt=str(row[6]),
            document_id=str(row[7]) if row[7] is not None else None,
            span_id=str(row[8]) if row[8] is not None else None,
            document_kind=str(row[9]) if row[9] is not None else None,
            section_path=str(row[10]) if row[10] is not None else None,
            precision=str(row[11]) if row[11] is not None else None,
            confidence=str(row[12]) if row[12] is not None else None,
        )

    def list_evidence_for_claim(self, *, claim_id: str) -> tuple[ClaimEvidencePointerRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
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
            FROM claim_evidence_pointers
            WHERE claim_id = ?
            ORDER BY id ASC
            """,
            (claim_id,),
        ).fetchall()
        return tuple(
            ClaimEvidencePointerRecord(
                id=str(row[0]),
                claim_id=str(row[1]),
                artifact_id=str(row[2]),
                section_ref=str(row[3]) if row[3] is not None else None,
                char_start=int(row[4]) if row[4] is not None else None,
                char_end=int(row[5]) if row[5] is not None else None,
                excerpt=str(row[6]),
                document_id=str(row[7]) if row[7] is not None else None,
                span_id=str(row[8]) if row[8] is not None else None,
                document_kind=str(row[9]) if row[9] is not None else None,
                section_path=str(row[10]) if row[10] is not None else None,
                precision=str(row[11]) if row[11] is not None else None,
                confidence=str(row[12]) if row[12] is not None else None,
            )
            for row in rows
        )

    def list_claims_for_publication(self, *, publication_id: str) -> tuple[PublicationClaimRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                publication_id,
                claim_order,
                claim_text
            FROM publication_claims
            WHERE publication_id = ?
            ORDER BY claim_order ASC
            """,
            (publication_id,),
        ).fetchall()
        return tuple(
            PublicationClaimRecord(
                id=str(row[0]),
                publication_id=str(row[1]),
                claim_order=int(row[2]),
                claim_text=str(row[3]),
            )
            for row in rows
        )