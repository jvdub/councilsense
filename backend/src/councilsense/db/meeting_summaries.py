from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal


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


class MeetingSummaryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

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
    ) -> SummaryPublicationRecord:
        with self._connection:
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
                    summary_text,
                    key_decisions_json,
                    key_actions_json,
                    notable_topics_json,
                    published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                """,
                (
                    publication_id,
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
            summary_text=str(row[7]),
            key_decisions_json=str(row[8]),
            key_actions_json=str(row[9]),
            notable_topics_json=str(row[10]),
            published_at=str(row[11]),
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
    ) -> ClaimEvidencePointerRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO claim_evidence_pointers (
                    id,
                    claim_id,
                    artifact_id,
                    section_ref,
                    char_start,
                    char_end,
                    excerpt
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (pointer_id, claim_id, artifact_id, section_ref, char_start, char_end, excerpt),
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
                excerpt
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
                excerpt
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