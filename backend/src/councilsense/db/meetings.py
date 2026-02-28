from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class MeetingRecord:
    id: str
    city_id: str
    meeting_uid: str
    title: str


class MissingMeetingCityError(ValueError):
    def __init__(self) -> None:
        super().__init__("Meeting city_id is required")


class InvalidMeetingCityError(ValueError):
    def __init__(self, city_id: str) -> None:
        self.city_id = city_id
        super().__init__(f"Unsupported or disabled city_id: {city_id}")


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