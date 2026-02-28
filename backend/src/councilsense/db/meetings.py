from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class MeetingDetailEvidencePointer:
    id: str
    artifact_id: str
    section_ref: str | None
    char_start: int | None
    char_end: int | None
    excerpt: str


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
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
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
    meeting_uid: str
    title: str
    created_at: str
    updated_at: str
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
            WHERE {where_sql}
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

        items = tuple(
            MeetingListItem(
                id=str(row[0]),
                city_id=str(row[1]),
                meeting_uid=str(row[2]),
                title=str(row[3]),
                created_at=str(row[4]),
                updated_at=str(row[5]),
                publication_status=str(row[6]) if row[6] is not None else None,
                confidence_label=str(row[7]) if row[7] is not None else None,
                reader_low_confidence=bool(row[8]),
            )
            for row in rows
        )

        next_cursor = None
        if len(items) == limit:
            last_item = items[-1]
            next_cursor = MeetingListCursor(created_at=last_item.created_at, meeting_id=last_item.id)

        return MeetingListPage(items=items, next_cursor=next_cursor)

    def get_meeting_detail(self, *, meeting_id: str) -> MeetingDetail | None:
        return self._get_meeting_detail(meeting_id=meeting_id)

    def get_meeting_detail_for_city(self, *, meeting_id: str, city_id: str) -> MeetingDetail | None:
        return self._get_meeting_detail(meeting_id=meeting_id, city_id=city_id)

    def _get_meeting_detail(self, *, meeting_id: str, city_id: str | None = None) -> MeetingDetail | None:
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
                sp.published_at
            FROM meetings m
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

        publication_id = str(meeting_row[6]) if meeting_row[6] is not None else None
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
                        excerpt
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
                        section_ref=str(evidence_row[2]) if evidence_row[2] is not None else None,
                        char_start=int(evidence_row[3]) if evidence_row[3] is not None else None,
                        char_end=int(evidence_row[4]) if evidence_row[4] is not None else None,
                        excerpt=str(evidence_row[5]),
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

        return MeetingDetail(
            id=str(meeting_row[0]),
            city_id=str(meeting_row[1]),
            meeting_uid=str(meeting_row[2]),
            title=str(meeting_row[3]),
            created_at=str(meeting_row[4]),
            updated_at=str(meeting_row[5]),
            publication_id=publication_id,
            publication_status=str(meeting_row[7]) if meeting_row[7] is not None else None,
            confidence_label=str(meeting_row[8]) if meeting_row[8] is not None else None,
            reader_low_confidence=bool(meeting_row[9]),
            summary_text=str(meeting_row[10]) if meeting_row[10] is not None else None,
            key_decisions=self._parse_string_list(meeting_row[11]),
            key_actions=self._parse_string_list(meeting_row[12]),
            notable_topics=self._parse_string_list(meeting_row[13]),
            published_at=str(meeting_row[14]) if meeting_row[14] is not None else None,
            claims=claims,
        )

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