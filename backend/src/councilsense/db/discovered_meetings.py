from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredMeetingIdentity:
    city_id: str
    city_source_id: str
    provider_name: str
    source_meeting_id: str


@dataclass(frozen=True)
class DiscoveredMeetingRecord:
    id: str
    city_id: str
    city_source_id: str
    provider_name: str
    source_meeting_id: str
    title: str
    meeting_date: str | None
    body_name: str | None
    source_url: str
    discovered_at: str
    synced_at: str
    meeting_id: str | None
    created_at: str
    updated_at: str


class DiscoveredMeetingRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def upsert_discovered_meeting(
        self,
        *,
        city_id: str,
        city_source_id: str,
        provider_name: str,
        source_meeting_id: str,
        title: str,
        meeting_date: str | None,
        body_name: str | None,
        source_url: str,
        synced_at: str,
        meeting_id: str | None = None,
    ) -> DiscoveredMeetingRecord:
        identity = DiscoveredMeetingIdentity(
            city_id=city_id.strip(),
            city_source_id=city_source_id.strip(),
            provider_name=provider_name.strip(),
            source_meeting_id=source_meeting_id.strip(),
        )
        discovered_meeting_id = build_discovered_meeting_id(identity=identity)
        normalized_title = title.strip()
        normalized_source_url = source_url.strip()
        normalized_synced_at = synced_at.strip()
        normalized_meeting_date = _normalize_optional_text(meeting_date)
        normalized_body_name = _normalize_optional_text(body_name)
        normalized_meeting_id = _normalize_optional_text(meeting_id)

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO discovered_meetings (
                    id,
                    city_id,
                    city_source_id,
                    provider_name,
                    source_meeting_id,
                    title,
                    meeting_date,
                    body_name,
                    source_url,
                    discovered_at,
                    synced_at,
                    meeting_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (city_id, city_source_id, source_meeting_id)
                DO UPDATE SET
                    provider_name = excluded.provider_name,
                    title = excluded.title,
                    meeting_date = excluded.meeting_date,
                    body_name = excluded.body_name,
                    source_url = excluded.source_url,
                    synced_at = excluded.synced_at,
                    meeting_id = COALESCE(excluded.meeting_id, discovered_meetings.meeting_id),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    discovered_meeting_id,
                    identity.city_id,
                    identity.city_source_id,
                    identity.provider_name,
                    identity.source_meeting_id,
                    normalized_title,
                    normalized_meeting_date,
                    normalized_body_name,
                    normalized_source_url,
                    normalized_synced_at,
                    normalized_synced_at,
                    normalized_meeting_id,
                ),
            )

        record = self.get_by_source_identity(
            city_id=identity.city_id,
            city_source_id=identity.city_source_id,
            source_meeting_id=identity.source_meeting_id,
        )
        assert record is not None
        return record

    def get_by_source_identity(
        self,
        *,
        city_id: str,
        city_source_id: str,
        source_meeting_id: str,
    ) -> DiscoveredMeetingRecord | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                city_id,
                city_source_id,
                provider_name,
                source_meeting_id,
                title,
                meeting_date,
                body_name,
                source_url,
                discovered_at,
                synced_at,
                meeting_id,
                created_at,
                updated_at
            FROM discovered_meetings
            WHERE city_id = ?
              AND city_source_id = ?
              AND source_meeting_id = ?
            """,
            (city_id.strip(), city_source_id.strip(), source_meeting_id.strip()),
        ).fetchone()
        if row is None:
            return None
        return _to_discovered_meeting_record(row)

    def list_for_source(self, *, city_source_id: str) -> tuple[DiscoveredMeetingRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                city_id,
                city_source_id,
                provider_name,
                source_meeting_id,
                title,
                meeting_date,
                body_name,
                source_url,
                discovered_at,
                synced_at,
                meeting_id,
                created_at,
                updated_at
            FROM discovered_meetings
            WHERE city_source_id = ?
            ORDER BY meeting_date DESC, synced_at DESC, id ASC
            """,
            (city_source_id.strip(),),
        ).fetchall()
        return tuple(_to_discovered_meeting_record(row) for row in rows)


def build_discovered_meeting_id(*, identity: DiscoveredMeetingIdentity) -> str:
    fingerprint = hashlib.sha256(
        "|".join((identity.city_id, identity.city_source_id, identity.source_meeting_id)).encode("utf-8")
    ).hexdigest()
    return f"discovered-{fingerprint[:16]}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _to_discovered_meeting_record(row: sqlite3.Row | tuple[object, ...]) -> DiscoveredMeetingRecord:
    return DiscoveredMeetingRecord(
        id=str(row[0]),
        city_id=str(row[1]),
        city_source_id=str(row[2]),
        provider_name=str(row[3]),
        source_meeting_id=str(row[4]),
        title=str(row[5]),
        meeting_date=str(row[6]) if row[6] is not None else None,
        body_name=str(row[7]) if row[7] is not None else None,
        source_url=str(row[8]),
        discovered_at=str(row[9]),
        synced_at=str(row[10]),
        meeting_id=str(row[11]) if row[11] is not None else None,
        created_at=str(row[12]),
        updated_at=str(row[13]),
    )