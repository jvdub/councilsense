from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class MeetingDetailEvidencePointer:
    id: str
    artifact_id: str
    source_document_url: str | None
    section_ref: str | None
    char_start: int | None
    char_end: int | None
    excerpt: str
    document_id: str | None = None
    span_id: str | None = None
    document_kind: str | None = None
    section_path: str | None = None
    precision: str | None = None
    confidence: str | None = None


@dataclass(frozen=True)
class MeetingIngestContext:
    body_name: str | None
    meeting_date: str | None
    candidate_url: str | None


@dataclass(frozen=True)
class MeetingSourceContext:
    document_kind: str | None
    source_document_url: str | None


@dataclass(frozen=True)
class MeetingDetailClaim:
    id: str
    claim_order: int
    claim_text: str
    evidence: tuple[MeetingDetailEvidencePointer, ...]


@dataclass(frozen=True)
class MeetingDetail:
    id: str
    city_id: str
    city_name: str | None
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
    meeting_date: str | None
    body_name: str | None
    source_document_kind: str | None
    source_document_url: str | None
    publication_id: str | None
    publication_status: str | None
    confidence_label: str | None
    reader_low_confidence: bool
    summary_text: str | None
    key_decisions: tuple[str, ...]
    key_actions: tuple[str, ...]
    notable_topics: tuple[str, ...]
    published_at: str | None
    claims: tuple[MeetingDetailClaim, ...]
    additive_blocks: Mapping[str, object] | None = None


@dataclass(frozen=True)
class MeetingRecord:
    id: str
    city_id: str
    meeting_uid: str
    title: str


@dataclass(frozen=True)
class MeetingListCursor:
    created_at: str
    meeting_id: str

    def to_token(self) -> str:
        return json.dumps(
            {
                "created_at": self.created_at,
                "meeting_id": self.meeting_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_token(cls, token: str) -> MeetingListCursor:
        try:
            payload = json.loads(token)
        except json.JSONDecodeError as exc:
            raise InvalidMeetingListCursorError() from exc

        if not isinstance(payload, dict):
            raise InvalidMeetingListCursorError()

        created_at = payload.get("created_at")
        meeting_id = payload.get("meeting_id")
        if not isinstance(created_at, str) or not created_at.strip():
            raise InvalidMeetingListCursorError()
        if not isinstance(meeting_id, str) or not meeting_id.strip():
            raise InvalidMeetingListCursorError()

        return cls(created_at=created_at.strip(), meeting_id=meeting_id.strip())


@dataclass(frozen=True)
class MeetingListItem:
    id: str
    city_id: str
    city_name: str | None
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
    meeting_date: str | None
    body_name: str | None
    publication_status: str | None
    confidence_label: str | None
    reader_low_confidence: bool


@dataclass(frozen=True)
class MeetingListPage:
    items: tuple[MeetingListItem, ...]
    next_cursor: MeetingListCursor | None


class MissingMeetingCityError(ValueError):
    def __init__(self) -> None:
        super().__init__("Meeting city_id is required")


class InvalidMeetingCityError(ValueError):
    def __init__(self, city_id: str) -> None:
        self.city_id = city_id
        super().__init__(f"Unsupported or disabled city_id: {city_id}")


class InvalidMeetingListCursorError(ValueError):
    def __init__(self) -> None:
        super().__init__("Invalid meeting list cursor")


class MeetingWriteRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert_meeting(
        self,
        *,
        meeting_id: str,
        meeting_uid: str,
        city_id: str | None,
        title: str,
    ) -> MeetingRecord:
        if city_id is None or not city_id.strip():
            raise MissingMeetingCityError()

        normalized_city_id = city_id.strip()
        if not self._is_enabled_city(normalized_city_id):
            raise InvalidMeetingCityError(normalized_city_id)

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO meetings (id, city_id, meeting_uid, title)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (city_id, meeting_uid)
                DO UPDATE SET
                    title = excluded.title,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (meeting_id, normalized_city_id, meeting_uid, title),
            )

        row = self._connection.execute(
            """
            SELECT id, city_id, meeting_uid, title
            FROM meetings
            WHERE city_id = ? AND meeting_uid = ?
            """,
            (normalized_city_id, meeting_uid),
        ).fetchone()
        assert row is not None

        return MeetingRecord(
            id=str(row[0]),
            city_id=str(row[1]),
            meeting_uid=str(row[2]),
            title=str(row[3]),
        )

    def _is_enabled_city(self, city_id: str) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM cities
            WHERE id = ?
              AND enabled = 1
            """,
            (city_id,),
        ).fetchone()
        return row is not None


class MeetingReadRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_city_meetings(
        self,
        *,
        city_id: str,
        limit: int,
        cursor: MeetingListCursor | None = None,
        start_created_at: str | None = None,
        end_created_at: str | None = None,
        publication_status: str | None = None,
    ) -> MeetingListPage:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        where_clauses: list[str] = ["m.city_id = ?"]
        params: list[str | int] = [city_id]

        if start_created_at is not None:
            where_clauses.append("m.created_at >= ?")
            params.append(start_created_at)

        if end_created_at is not None:
            where_clauses.append("m.created_at <= ?")
            params.append(end_created_at)

        if cursor is not None:
            where_clauses.append("(m.created_at < ? OR (m.created_at = ? AND m.id < ?))")
            params.extend((cursor.created_at, cursor.created_at, cursor.meeting_id))

        if publication_status is not None:
            where_clauses.append(
                """
                (
                    SELECT sp.publication_status
                    FROM summary_publications sp
                    WHERE sp.meeting_id = m.id
                    ORDER BY sp.published_at DESC, sp.id DESC
                    LIMIT 1
                ) = ?
                """
            )
            params.append(publication_status)

        where_sql = " AND ".join(clause.strip() for clause in where_clauses)
        params.append(limit)

        rows = self._connection.execute(
            f"""
            SELECT
                m.id,
                m.city_id,
                c.name,
                m.meeting_uid,
                m.title,
                m.created_at,
                m.updated_at,
                (
                    SELECT sp.publication_status
                    FROM summary_publications sp
                    WHERE sp.meeting_id = m.id
                    ORDER BY sp.published_at DESC, sp.id DESC
                    LIMIT 1
                ) AS publication_status,
                (
                    SELECT sp.confidence_label
                    FROM summary_publications sp
                    WHERE sp.meeting_id = m.id
                    ORDER BY sp.published_at DESC, sp.id DESC
                    LIMIT 1
                ) AS confidence_label,
                CASE
                    WHEN (
                        SELECT sp.confidence_label
                        FROM summary_publications sp
                        WHERE sp.meeting_id = m.id
                        ORDER BY sp.published_at DESC, sp.id DESC
                        LIMIT 1
                    ) IN ('low', 'limited_confidence') THEN 1
                    ELSE 0
                END AS reader_low_confidence
            FROM meetings m
            INNER JOIN cities c ON c.id = m.city_id
            WHERE {where_sql}
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

        items_list: list[MeetingListItem] = []
        for row in rows:
            ingest_context = self._lookup_ingest_context(meeting_id=str(row[0]))
            items_list.append(
                MeetingListItem(
                    id=str(row[0]),
                    city_id=str(row[1]),
                    city_name=str(row[2]) if row[2] is not None else None,
                    meeting_uid=str(row[3]),
                    title=str(row[4]),
                    created_at=str(row[5]),
                    updated_at=str(row[6]),
                    meeting_date=self._resolve_meeting_date(
                        created_at=str(row[5]),
                        ingest_context=ingest_context,
                    ),
                    body_name=ingest_context.body_name,
                    publication_status=str(row[7]) if row[7] is not None else None,
                    confidence_label=str(row[8]) if row[8] is not None else None,
                    reader_low_confidence=bool(row[9]),
                )
            )

        items = tuple(items_list)

        next_cursor = None
        if len(items) == limit:
            last_item = items[-1]
            next_cursor = MeetingListCursor(created_at=last_item.created_at, meeting_id=last_item.id)

        return MeetingListPage(items=items, next_cursor=next_cursor)

    def get_meeting_detail(self, *, meeting_id: str, include_additive_blocks: bool = False) -> MeetingDetail | None:
        return self._get_meeting_detail(meeting_id=meeting_id, include_additive_blocks=include_additive_blocks)

    def get_meeting_detail_for_city(
        self,
        *,
        meeting_id: str,
        city_id: str,
        include_additive_blocks: bool = False,
    ) -> MeetingDetail | None:
        return self._get_meeting_detail(
            meeting_id=meeting_id,
            city_id=city_id,
            include_additive_blocks=include_additive_blocks,
        )

    def _get_meeting_detail(
        self,
        *,
        meeting_id: str,
        city_id: str | None = None,
        include_additive_blocks: bool = False,
    ) -> MeetingDetail | None:
        where_sql = "WHERE m.id = ?"
        params: list[str] = [meeting_id]
        if city_id is not None:
            where_sql += " AND m.city_id = ?"
            params.append(city_id)

        meeting_row = self._connection.execute(
            f"""
            SELECT
                m.id,
                m.city_id,
                c.name,
                m.meeting_uid,
                m.title,
                m.created_at,
                m.updated_at,
                sp.id,
                sp.publication_status,
                sp.confidence_label,
                CASE
                    WHEN sp.confidence_label IN ('low', 'limited_confidence') THEN 1
                    ELSE 0
                END,
                sp.summary_text,
                sp.key_decisions_json,
                sp.key_actions_json,
                sp.notable_topics_json,
                                sp.published_at,
                                sp.publish_stage_outcome_id
            FROM meetings m
                        INNER JOIN cities c ON c.id = m.city_id
            LEFT JOIN summary_publications sp
              ON sp.id = (
                SELECT sp2.id
                FROM summary_publications sp2
                WHERE sp2.meeting_id = m.id
                ORDER BY sp2.published_at DESC, sp2.id DESC
                LIMIT 1
              )
            {where_sql}
            """,
            tuple(params),
        ).fetchone()

        if meeting_row is None:
            return None

        publication_id = str(meeting_row[7]) if meeting_row[7] is not None else None
        publish_stage_outcome_id = str(meeting_row[16]) if meeting_row[16] is not None else None
        ingest_context = self._lookup_ingest_context(meeting_id=meeting_id)
        source_context = self._lookup_source_context(meeting_id=meeting_id, ingest_context=ingest_context)
        claims: tuple[MeetingDetailClaim, ...] = ()
        if publication_id is not None:
            claim_rows = self._connection.execute(
                """
                SELECT id, claim_order, claim_text
                FROM publication_claims
                WHERE publication_id = ?
                ORDER BY claim_order ASC
                """,
                (publication_id,),
            ).fetchall()

            claim_items: list[MeetingDetailClaim] = []
            for claim_row in claim_rows:
                claim_id = str(claim_row[0])
                evidence_rows = self._connection.execute(
                    """
                    SELECT
                        id,
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
                evidence = tuple(
                    MeetingDetailEvidencePointer(
                        id=str(evidence_row[0]),
                        artifact_id=str(evidence_row[1]),
                        source_document_url=source_context.source_document_url,
                        section_ref=str(evidence_row[2]) if evidence_row[2] is not None else None,
                        char_start=int(evidence_row[3]) if evidence_row[3] is not None else None,
                        char_end=int(evidence_row[4]) if evidence_row[4] is not None else None,
                        excerpt=str(evidence_row[5]),
                        document_id=str(evidence_row[6]) if evidence_row[6] is not None else None,
                        span_id=str(evidence_row[7]) if evidence_row[7] is not None else None,
                        document_kind=str(evidence_row[8]) if evidence_row[8] is not None else None,
                        section_path=str(evidence_row[9]) if evidence_row[9] is not None else None,
                        precision=str(evidence_row[10]) if evidence_row[10] is not None else None,
                        confidence=str(evidence_row[11]) if evidence_row[11] is not None else None,
                    )
                    for evidence_row in evidence_rows
                )
                claim_items.append(
                    MeetingDetailClaim(
                        id=claim_id,
                        claim_order=int(claim_row[1]),
                        claim_text=str(claim_row[2]),
                        evidence=evidence,
                    )
                )
            claims = tuple(claim_items)

        additive_blocks = None
        if include_additive_blocks and publish_stage_outcome_id is not None:
            additive_blocks = self._lookup_additive_blocks(
                publish_stage_outcome_id=publish_stage_outcome_id,
            )

        return MeetingDetail(
            id=str(meeting_row[0]),
            city_id=str(meeting_row[1]),
            city_name=str(meeting_row[2]) if meeting_row[2] is not None else None,
            meeting_uid=str(meeting_row[3]),
            title=str(meeting_row[4]),
            created_at=str(meeting_row[5]),
            updated_at=str(meeting_row[6]),
            meeting_date=self._resolve_meeting_date(
                created_at=str(meeting_row[5]),
                ingest_context=ingest_context,
            ),
            body_name=ingest_context.body_name,
            source_document_kind=source_context.document_kind,
            source_document_url=source_context.source_document_url,
            publication_id=publication_id,
            publication_status=str(meeting_row[8]) if meeting_row[8] is not None else None,
            confidence_label=str(meeting_row[9]) if meeting_row[9] is not None else None,
            reader_low_confidence=bool(meeting_row[10]),
            summary_text=str(meeting_row[11]) if meeting_row[11] is not None else None,
            key_decisions=self._parse_string_list(meeting_row[12]),
            key_actions=self._parse_string_list(meeting_row[13]),
            notable_topics=self._parse_string_list(meeting_row[14]),
            published_at=str(meeting_row[15]) if meeting_row[15] is not None else None,
            claims=claims,
            additive_blocks=additive_blocks,
        )

    def _lookup_ingest_context(self, *, meeting_id: str) -> MeetingIngestContext:
        row = self._connection.execute(
            """
            SELECT metadata_json
            FROM processing_stage_outcomes
            WHERE meeting_id = ?
              AND stage_name = 'ingest'
            ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
            LIMIT 1
            """,
            (meeting_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return MeetingIngestContext(body_name=None, meeting_date=None, candidate_url=None)

        try:
            parsed = json.loads(str(row[0]))
        except json.JSONDecodeError:
            return MeetingIngestContext(body_name=None, meeting_date=None, candidate_url=None)

        if not isinstance(parsed, dict):
            return MeetingIngestContext(body_name=None, meeting_date=None, candidate_url=None)

        raw_body_name = parsed.get("selected_event_name")
        raw_meeting_date = parsed.get("selected_event_date") or parsed.get("meeting_date")
        raw_candidate_url = parsed.get("candidate_url")
        return MeetingIngestContext(
            body_name=raw_body_name.strip() if isinstance(raw_body_name, str) and raw_body_name.strip() else None,
            meeting_date=raw_meeting_date.strip() if isinstance(raw_meeting_date, str) and raw_meeting_date.strip() else None,
            candidate_url=(
                raw_candidate_url.strip() if isinstance(raw_candidate_url, str) and raw_candidate_url.strip() else None
            ),
        )

    def _lookup_source_context(
        self,
        *,
        meeting_id: str,
        ingest_context: MeetingIngestContext,
    ) -> MeetingSourceContext:
        row = self._connection.execute(
            """
            SELECT document_kind, source_document_url
            FROM canonical_documents
            WHERE meeting_id = ?
              AND is_active_revision = 1
            ORDER BY
              CASE document_kind
                WHEN 'minutes' THEN 0
                WHEN 'agenda' THEN 1
                WHEN 'packet' THEN 2
                ELSE 3
              END ASC,
              revision_number DESC,
              created_at DESC,
              id DESC
            LIMIT 1
            """,
            (meeting_id,),
        ).fetchone()
        if row is not None:
            return MeetingSourceContext(
                document_kind=str(row[0]) if row[0] is not None else None,
                source_document_url=(
                    str(row[1]).strip()
                    if row[1] is not None and str(row[1]).strip()
                    else ingest_context.candidate_url
                ),
            )

        return MeetingSourceContext(
            document_kind=None,
            source_document_url=ingest_context.candidate_url,
        )

    def _resolve_meeting_date(self, *, created_at: str, ingest_context: MeetingIngestContext) -> str | None:
        if ingest_context.meeting_date is not None:
            return ingest_context.meeting_date

        created_value = created_at.strip()
        if len(created_value) >= 10:
            return created_value[:10]
        return None

    def _lookup_additive_blocks(self, *, publish_stage_outcome_id: str) -> Mapping[str, object] | None:
        row = self._connection.execute(
            """
            SELECT metadata_json
            FROM processing_stage_outcomes
            WHERE id = ?
            """,
            (publish_stage_outcome_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return None

        try:
            parsed = json.loads(str(row[0]))
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None

        candidate_blocks: dict[str, object] = {}
        root_mapping = parsed if isinstance(parsed, Mapping) else {}
        nested_blocks = root_mapping.get("additive_blocks")
        if isinstance(nested_blocks, Mapping):
            for block_name in ("planned", "outcomes", "planned_outcome_mismatches"):
                block_value = nested_blocks.get(block_name)
                if isinstance(block_value, Mapping):
                    candidate_blocks[block_name] = dict(block_value)

        for block_name in ("planned", "outcomes", "planned_outcome_mismatches"):
            block_value = root_mapping.get(block_name)
            if isinstance(block_value, Mapping):
                candidate_blocks[block_name] = dict(block_value)

        return candidate_blocks or None

    def _lookup_source_document_url(self, *, meeting_id: str) -> str | None:
        source_context = self._lookup_source_context(
            meeting_id=meeting_id,
            ingest_context=self._lookup_ingest_context(meeting_id=meeting_id),
        )
        return source_context.source_document_url

    def _parse_string_list(self, value: object) -> tuple[str, ...]:
        if value is None:
            return ()

        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return ()

        if not isinstance(parsed, list):
            return ()

        return tuple(str(item) for item in parsed if isinstance(item, str))

    def explain_city_meetings_query_plan(
        self,
        *,
        city_id: str,
        limit: int,
        publication_status: str | None = None,
    ) -> tuple[str, ...]:
        where_clauses: list[str] = ["m.city_id = ?"]
        params: list[str | int] = [city_id]

        if publication_status is not None:
            where_clauses.append(
                """
                (
                    SELECT sp.publication_status
                    FROM summary_publications sp
                    WHERE sp.meeting_id = m.id
                    ORDER BY sp.published_at DESC, sp.id DESC
                    LIMIT 1
                ) = ?
                """
            )
            params.append(publication_status)

        where_sql = " AND ".join(clause.strip() for clause in where_clauses)
        params.append(limit)

        plan_rows = self._connection.execute(
            f"""
            EXPLAIN QUERY PLAN
            SELECT
                m.id,
                m.created_at,
                (
                    SELECT sp.publication_status
                    FROM summary_publications sp
                    WHERE sp.meeting_id = m.id
                    ORDER BY sp.published_at DESC, sp.id DESC
                    LIMIT 1
                ) AS publication_status
            FROM meetings m
            WHERE {where_sql}
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

        return tuple(str(row[3]) for row in plan_rows)