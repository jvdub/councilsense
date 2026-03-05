from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any
from typing import Literal
from typing import cast


ArtifactKind = Literal["raw", "normalized"]


@dataclass(frozen=True)
class CanonicalDocumentArtifactRecord:
    id: str
    canonical_document_id: str
    artifact_kind: ArtifactKind
    storage_uri: str | None
    content_checksum: str
    lineage_parent_artifact_id: str | None
    lineage_root_checksum: str
    lineage_depth: int
    normalizer_name: str | None
    normalizer_version: str | None
    created_at: str
    updated_at: str


class CanonicalDocumentArtifactRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert_artifact(
        self,
        *,
        artifact_id: str,
        canonical_document_id: str,
        artifact_kind: ArtifactKind,
        content_checksum: str,
        storage_uri: str | None,
        lineage_parent_artifact_id: str | None,
        normalizer_name: str | None,
        normalizer_version: str | None,
    ) -> CanonicalDocumentArtifactRecord:
        lineage_root_checksum = content_checksum
        lineage_depth = 0

        if lineage_parent_artifact_id is not None:
            parent = self._connection.execute(
                """
                SELECT
                    canonical_document_id,
                    lineage_root_checksum,
                    lineage_depth
                FROM canonical_document_artifacts
                WHERE id = ?
                """,
                (lineage_parent_artifact_id,),
            ).fetchone()
            if parent is None:
                raise ValueError("lineage_parent_artifact_id does not reference an existing artifact")
            if str(parent[0]) != canonical_document_id:
                raise ValueError("lineage_parent_artifact_id must belong to the same canonical_document_id")
            lineage_root_checksum = str(parent[1])
            lineage_depth = int(parent[2]) + 1

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO canonical_document_artifacts (
                    id,
                    canonical_document_id,
                    artifact_kind,
                    storage_uri,
                    content_checksum,
                    lineage_parent_artifact_id,
                    lineage_root_checksum,
                    lineage_depth,
                    normalizer_name,
                    normalizer_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (canonical_document_id, artifact_kind, content_checksum)
                DO UPDATE SET
                    storage_uri = COALESCE(canonical_document_artifacts.storage_uri, excluded.storage_uri),
                    normalizer_name = COALESCE(canonical_document_artifacts.normalizer_name, excluded.normalizer_name),
                    normalizer_version = COALESCE(canonical_document_artifacts.normalizer_version, excluded.normalizer_version),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    artifact_id,
                    canonical_document_id,
                    artifact_kind,
                    storage_uri,
                    content_checksum,
                    lineage_parent_artifact_id,
                    lineage_root_checksum,
                    lineage_depth,
                    normalizer_name,
                    normalizer_version,
                ),
            )

        row = self._connection.execute(
            """
            SELECT
                id,
                canonical_document_id,
                artifact_kind,
                storage_uri,
                content_checksum,
                lineage_parent_artifact_id,
                lineage_root_checksum,
                lineage_depth,
                normalizer_name,
                normalizer_version,
                created_at,
                updated_at
            FROM canonical_document_artifacts
            WHERE canonical_document_id = ?
              AND artifact_kind = ?
              AND content_checksum = ?
            """,
            (canonical_document_id, artifact_kind, content_checksum),
        ).fetchone()
        assert row is not None
        return _to_record(row)

    def get_artifact_by_checksum(
        self,
        *,
        canonical_document_id: str,
        content_checksum: str,
        artifact_kind: ArtifactKind,
    ) -> CanonicalDocumentArtifactRecord | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                canonical_document_id,
                artifact_kind,
                storage_uri,
                content_checksum,
                lineage_parent_artifact_id,
                lineage_root_checksum,
                lineage_depth,
                normalizer_name,
                normalizer_version,
                created_at,
                updated_at
            FROM canonical_document_artifacts
            WHERE canonical_document_id = ?
              AND artifact_kind = ?
              AND content_checksum = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (canonical_document_id, artifact_kind, content_checksum),
        ).fetchone()
        if row is None:
            return None
        return _to_record(row)

    def list_lineage_chain(self, *, artifact_id: str) -> tuple[CanonicalDocumentArtifactRecord, ...]:
        rows = self._connection.execute(
            """
            WITH RECURSIVE lineage AS (
                SELECT
                    id,
                    canonical_document_id,
                    artifact_kind,
                    storage_uri,
                    content_checksum,
                    lineage_parent_artifact_id,
                    lineage_root_checksum,
                    lineage_depth,
                    normalizer_name,
                    normalizer_version,
                    created_at,
                    updated_at
                FROM canonical_document_artifacts
                WHERE id = ?
                UNION ALL
                SELECT
                    parent.id,
                    parent.canonical_document_id,
                    parent.artifact_kind,
                    parent.storage_uri,
                    parent.content_checksum,
                    parent.lineage_parent_artifact_id,
                    parent.lineage_root_checksum,
                    parent.lineage_depth,
                    parent.normalizer_name,
                    parent.normalizer_version,
                    parent.created_at,
                    parent.updated_at
                FROM canonical_document_artifacts parent
                INNER JOIN lineage child ON child.lineage_parent_artifact_id = parent.id
            )
            SELECT
                id,
                canonical_document_id,
                artifact_kind,
                storage_uri,
                content_checksum,
                lineage_parent_artifact_id,
                lineage_root_checksum,
                lineage_depth,
                normalizer_name,
                normalizer_version,
                created_at,
                updated_at
            FROM lineage
            ORDER BY lineage_depth ASC, created_at ASC, id ASC
            """,
            (artifact_id,),
        ).fetchall()
        return tuple(_to_record(row) for row in rows)


def _to_record(row: sqlite3.Row | tuple[Any, ...]) -> CanonicalDocumentArtifactRecord:
    artifact_kind = cast(ArtifactKind, str(row[2]))
    return CanonicalDocumentArtifactRecord(
        id=str(row[0]),
        canonical_document_id=str(row[1]),
        artifact_kind=artifact_kind,
        storage_uri=str(row[3]) if row[3] is not None else None,
        content_checksum=str(row[4]),
        lineage_parent_artifact_id=str(row[5]) if row[5] is not None else None,
        lineage_root_checksum=str(row[6]),
        lineage_depth=int(row[7]),
        normalizer_name=str(row[8]) if row[8] is not None else None,
        normalizer_version=str(row[9]) if row[9] is not None else None,
        created_at=str(row[10]),
        updated_at=str(row[11]),
    )
