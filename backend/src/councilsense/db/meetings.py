from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


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
                ) AS confidence_label
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
            )
            for row in rows
        )

        next_cursor = None
        if len(items) == limit:
            last_item = items[-1]
            next_cursor = MeetingListCursor(created_at=last_item.created_at, meeting_id=last_item.id)

        return MeetingListPage(items=items, next_cursor=next_cursor)

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