from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from councilsense.app.provider_enumeration import EnumeratedMeeting, get_source_meeting_enumeration_provider
from councilsense.db.city_registry import CityRegistryRepository, ConfiguredCitySelectionService
from councilsense.db import DiscoveredMeetingIdentity, DiscoveredMeetingRecord, DiscoveredMeetingRepository, build_discovered_meeting_id


DISCOVERY_SYNC_IDEMPOTENCY_KEY_VERSION = "st036-discovery-idem-v1"
DISCOVERY_SYNC_DEDUPE_KEY_VERSION = "st036-discovery-dedupe-v1"
DEFAULT_STARTUP_DISCOVERY_TIMEOUT_SECONDS = 8.0


DiscoverySyncOutcome = Literal["accepted", "metadata_refreshed", "duplicate_suppressed"]


@dataclass(frozen=True)
class DiscoverySyncDiagnostic:
    code: str
    city_id: str
    city_source_id: str
    provider_name: str
    source_meeting_id: str
    discovered_meeting_id: str
    idempotency_key: str
    dedupe_key: str
    outcome: DiscoverySyncOutcome
    detail: str


@dataclass(frozen=True)
class DiscoverySyncResult:
    synced_count: int
    reconciled_count: int
    errors: tuple[str, ...]
    diagnostics: tuple[DiscoverySyncDiagnostic, ...] = ()


def run_startup_discovery_sync(
    *,
    connection: sqlite3.Connection,
    supported_city_ids: tuple[str, ...],
    timeout_seconds: float = DEFAULT_STARTUP_DISCOVERY_TIMEOUT_SECONDS,
    fetch_url: Callable[[str, float], bytes] | None = None,
) -> DiscoverySyncResult:
    selection_service = ConfiguredCitySelectionService(CityRegistryRepository(connection))
    supported_city_id_set = {city_id.strip() for city_id in supported_city_ids if city_id.strip()}
    resolved_fetch_url = fetch_url or _fetch_url_bytes
    synced_count = 0
    reconciled_count = 0
    errors: list[str] = []
    diagnostics: list[DiscoverySyncDiagnostic] = []
    synced_at = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

    for city_config in selection_service.list_enabled_city_configs():
        if supported_city_id_set and city_config.city.id not in supported_city_id_set:
            continue

        for source in city_config.sources:
            try:
                provider = get_source_meeting_enumeration_provider(source)
                enumerated_meetings = provider.enumerate_meetings(
                    source=source,
                    timeout_seconds=timeout_seconds,
                    fetch_url=resolved_fetch_url,
                )
            except Exception as exc:
                errors.append(f"Startup discovery sync failed for source_id={source.id}: {exc}")
                continue

            sync_result = sync_enumerated_meetings(
                connection=connection,
                enumerated_meetings=enumerated_meetings,
                synced_at=synced_at,
            )
            synced_count += sync_result.synced_count
            diagnostics.extend(sync_result.diagnostics)
            errors.extend(sync_result.errors)

            reconcile_result = reconcile_discovered_meetings(
                connection=connection,
                city_id=source.city_id,
                city_source_id=source.id,
            )
            reconciled_count += reconcile_result.reconciled_count
            errors.extend(reconcile_result.errors)

    return DiscoverySyncResult(
        synced_count=synced_count,
        reconciled_count=reconciled_count,
        errors=tuple(errors),
        diagnostics=tuple(diagnostics),
    )


def _fetch_url_bytes(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": "CouncilSense discovery sync"})
    with urlopen(request, timeout=max(timeout_seconds, 1.0)) as response:
        return response.read()


def build_discovery_sync_idempotency_key(
    *,
    city_id: str,
    city_source_id: str,
    provider_name: str,
    source_meeting_id: str,
) -> str:
    normalized_city_id = city_id.strip()
    normalized_city_source_id = city_source_id.strip()
    normalized_provider_name = provider_name.strip().lower()
    normalized_source_meeting_id = source_meeting_id.strip()
    return ":".join(
        (
            DISCOVERY_SYNC_IDEMPOTENCY_KEY_VERSION,
            normalized_city_id,
            normalized_city_source_id,
            normalized_provider_name,
            normalized_source_meeting_id,
        )
    )


def build_discovery_sync_dedupe_key(
    *,
    city_id: str,
    city_source_id: str,
    provider_name: str,
    source_meeting_id: str,
) -> str:
    idempotency_key = build_discovery_sync_idempotency_key(
        city_id=city_id,
        city_source_id=city_source_id,
        provider_name=provider_name,
        source_meeting_id=source_meeting_id,
    )
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"{DISCOVERY_SYNC_DEDUPE_KEY_VERSION}:{digest}"


def sync_enumerated_meetings(
    *,
    connection: sqlite3.Connection,
    enumerated_meetings: tuple[EnumeratedMeeting, ...],
    synced_at: str,
) -> DiscoverySyncResult:
    repository = DiscoveredMeetingRepository(connection)
    errors: list[str] = []
    diagnostics: list[DiscoverySyncDiagnostic] = []
    synced_count = 0

    for enumerated in enumerated_meetings:
        try:
            diagnostic = _sync_enumerated_meeting(
                repository=repository,
                enumerated=enumerated,
                synced_at=synced_at,
            )
        except Exception as exc:
            errors.append(
                f"Failed to persist discovered meeting {enumerated.identity.source_meeting_id}: {exc}"
            )
            continue
        diagnostics.append(diagnostic)
        synced_count += 1

    return DiscoverySyncResult(
        synced_count=synced_count,
        reconciled_count=0,
        errors=tuple(errors),
        diagnostics=tuple(diagnostics),
    )


def reconcile_discovered_meetings(
    *,
    connection: sqlite3.Connection,
    city_id: str,
    city_source_id: str,
) -> DiscoverySyncResult:
    repository = DiscoveredMeetingRepository(connection)
    discovered_meetings = tuple(
        meeting
        for meeting in repository.list_for_source(city_source_id=city_source_id)
        if meeting.city_id == city_id and meeting.meeting_id is None
    )
    if not discovered_meetings:
        return DiscoverySyncResult(synced_count=0, reconciled_count=0, errors=(), diagnostics=())

    match_index = _build_ingest_match_index(connection=connection, city_id=city_id)
    errors: list[str] = []
    reconciled_count = 0

    for discovered in discovered_meetings:
        meeting_id = _resolve_matching_meeting_id(match_index=match_index, discovered_source=discovered)
        if meeting_id is None:
            continue

        try:
            repository.upsert_discovered_meeting(
                city_id=discovered.city_id,
                city_source_id=discovered.city_source_id,
                provider_name=discovered.provider_name,
                source_meeting_id=discovered.source_meeting_id,
                title=discovered.title,
                meeting_date=discovered.meeting_date,
                body_name=discovered.body_name,
                source_url=discovered.source_url,
                synced_at=discovered.synced_at,
                meeting_id=meeting_id,
            )
        except Exception as exc:
            errors.append(
                f"Failed to reconcile discovered meeting {discovered.source_meeting_id}: {exc}"
            )
            continue
        reconciled_count += 1

    return DiscoverySyncResult(
        synced_count=0,
        reconciled_count=reconciled_count,
        errors=tuple(errors),
        diagnostics=(),
    )


def _sync_enumerated_meeting(
    *,
    repository: DiscoveredMeetingRepository,
    enumerated: EnumeratedMeeting,
    synced_at: str,
) -> DiscoverySyncDiagnostic:
    identity = DiscoveredMeetingIdentity(
        city_id=enumerated.identity.city_id.strip(),
        city_source_id=enumerated.identity.city_source_id.strip(),
        provider_name=enumerated.identity.provider_name.strip().lower(),
        source_meeting_id=enumerated.identity.source_meeting_id.strip(),
    )
    discovered_meeting_id = build_discovered_meeting_id(identity=identity)
    idempotency_key = build_discovery_sync_idempotency_key(
        city_id=identity.city_id,
        city_source_id=identity.city_source_id,
        provider_name=identity.provider_name,
        source_meeting_id=identity.source_meeting_id,
    )
    dedupe_key = build_discovery_sync_dedupe_key(
        city_id=identity.city_id,
        city_source_id=identity.city_source_id,
        provider_name=identity.provider_name,
        source_meeting_id=identity.source_meeting_id,
    )
    source_type = _lookup_source_type(connection=repository._connection, city_source_id=identity.city_source_id)

    if source_type != "minutes" and repository.has_event_for_source_type(
        city_id=identity.city_id,
        provider_name=identity.provider_name,
        source_meeting_id=identity.source_meeting_id,
        source_type="minutes",
    ):
        return DiscoverySyncDiagnostic(
            code="discovered_meeting_sync_duplicate_suppressed",
            city_id=identity.city_id,
            city_source_id=identity.city_source_id,
            provider_name=identity.provider_name,
            source_meeting_id=identity.source_meeting_id,
            discovered_meeting_id=discovered_meeting_id,
            idempotency_key=idempotency_key,
            dedupe_key=dedupe_key,
            outcome="duplicate_suppressed",
            detail="supplemental source discovery suppressed because a minutes-backed event already exists",
        )

    normalized_title = enumerated.title.strip()
    normalized_meeting_date = _normalize_text(enumerated.meeting_date)
    normalized_body_name = _normalize_text(enumerated.body_name)
    normalized_source_url = _normalize_url(enumerated.source_url)
    normalized_synced_at = synced_at.strip()

    inserted = _insert_discovered_meeting_if_absent(
        connection=repository._connection,
        identity=identity,
        discovered_meeting_id=discovered_meeting_id,
        title=normalized_title,
        meeting_date=normalized_meeting_date,
        body_name=normalized_body_name,
        source_url=normalized_source_url,
        synced_at=normalized_synced_at,
    )
    current = repository.get_by_source_identity(
        city_id=identity.city_id,
        city_source_id=identity.city_source_id,
        source_meeting_id=identity.source_meeting_id,
    )
    assert current is not None

    if inserted:
        detail = "discovered meeting inserted as canonical row for stable source identity"
        if source_type == "minutes":
            removed_count = repository.delete_event_for_other_source_types(
                city_id=identity.city_id,
                provider_name=identity.provider_name,
                source_meeting_id=identity.source_meeting_id,
                keep_source_type="minutes",
            )
            if removed_count > 0:
                detail = f"{detail}; removed {removed_count} supplemental duplicate(s)"
        return DiscoverySyncDiagnostic(
            code="discovered_meeting_sync_accepted",
            city_id=identity.city_id,
            city_source_id=identity.city_source_id,
            provider_name=identity.provider_name,
            source_meeting_id=identity.source_meeting_id,
            discovered_meeting_id=current.id,
            idempotency_key=idempotency_key,
            dedupe_key=dedupe_key,
            outcome="accepted",
            detail=detail,
        )

    if _discovered_meeting_needs_refresh(
        current=current,
        title=normalized_title,
        meeting_date=normalized_meeting_date,
        body_name=normalized_body_name,
        source_url=normalized_source_url,
        synced_at=normalized_synced_at,
    ):
        refreshed = repository.upsert_discovered_meeting(
            city_id=identity.city_id,
            city_source_id=identity.city_source_id,
            provider_name=identity.provider_name,
            source_meeting_id=identity.source_meeting_id,
            title=normalized_title,
            meeting_date=normalized_meeting_date,
            body_name=normalized_body_name,
            source_url=normalized_source_url or "",
            synced_at=normalized_synced_at,
            meeting_id=current.meeting_id,
        )
        detail = "duplicate source identity reused the canonical row and refreshed mutable metadata"
        if source_type == "minutes":
            removed_count = repository.delete_event_for_other_source_types(
                city_id=identity.city_id,
                provider_name=identity.provider_name,
                source_meeting_id=identity.source_meeting_id,
                keep_source_type="minutes",
            )
            if removed_count > 0:
                detail = f"{detail}; removed {removed_count} supplemental duplicate(s)"
        return DiscoverySyncDiagnostic(
            code="discovered_meeting_sync_metadata_refreshed",
            city_id=identity.city_id,
            city_source_id=identity.city_source_id,
            provider_name=identity.provider_name,
            source_meeting_id=identity.source_meeting_id,
            discovered_meeting_id=refreshed.id,
            idempotency_key=idempotency_key,
            dedupe_key=dedupe_key,
            outcome="metadata_refreshed",
            detail=detail,
        )

    return DiscoverySyncDiagnostic(
        code="discovered_meeting_sync_duplicate_suppressed",
        city_id=identity.city_id,
        city_source_id=identity.city_source_id,
        provider_name=identity.provider_name,
        source_meeting_id=identity.source_meeting_id,
        discovered_meeting_id=current.id,
        idempotency_key=idempotency_key,
        dedupe_key=dedupe_key,
        outcome="duplicate_suppressed",
        detail="duplicate discovery write suppressed because canonical row already matched incoming metadata",
    )


def _lookup_source_type(*, connection: sqlite3.Connection, city_source_id: str) -> str:
    row = connection.execute(
        "SELECT source_type FROM city_sources WHERE id = ?",
        (city_source_id.strip(),),
    ).fetchone()
    if row is None or row[0] is None:
        raise LookupError(f"Configured source not found: city_source_id={city_source_id}")
    return str(row[0]).strip().lower()


def _insert_discovered_meeting_if_absent(
    *,
    connection: sqlite3.Connection,
    identity: DiscoveredMeetingIdentity,
    discovered_meeting_id: str,
    title: str,
    meeting_date: str | None,
    body_name: str | None,
    source_url: str | None,
    synced_at: str,
) -> bool:
    with connection:
        cursor = connection.execute(
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT (city_id, city_source_id, source_meeting_id) DO NOTHING
            """,
            (
                discovered_meeting_id,
                identity.city_id,
                identity.city_source_id,
                identity.provider_name,
                identity.source_meeting_id,
                title,
                meeting_date,
                body_name,
                source_url or "",
                synced_at,
                synced_at,
            ),
        )
    return cursor.rowcount == 1


def _discovered_meeting_needs_refresh(
    *,
    current: DiscoveredMeetingRecord,
    title: str,
    meeting_date: str | None,
    body_name: str | None,
    source_url: str | None,
    synced_at: str,
) -> bool:
    return (
        current.title != title
        or current.meeting_date != meeting_date
        or current.body_name != body_name
        or _normalize_url(current.source_url) != source_url
        or current.synced_at != synced_at
    )


@dataclass(frozen=True)
class _IngestSourceIdentity:
    selected_event_id: str | None
    source_meeting_url: str | None


@dataclass
class _IngestMatchIndex:
    by_event_id: dict[str, str | None]
    by_source_meeting_url: dict[str, str | None]


def _build_ingest_match_index(*, connection: sqlite3.Connection, city_id: str) -> _IngestMatchIndex:
    rows = connection.execute(
        """
        SELECT meeting_id, metadata_json
        FROM processing_stage_outcomes
        WHERE city_id = ?
          AND stage_name = 'ingest'
          AND metadata_json IS NOT NULL
        ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
        """,
        (city_id.strip(),),
    ).fetchall()

    by_event_id: dict[str, str | None] = {}
    by_source_meeting_url: dict[str, str | None] = {}
    for row in rows:
        meeting_id = str(row[0]).strip()
        identity = _extract_ingest_source_identity(row[1])
        if identity is None:
            continue
        if identity.selected_event_id is not None:
            _record_unique_match(by_event_id, identity.selected_event_id, meeting_id)
        if identity.source_meeting_url is not None:
            _record_unique_match(by_source_meeting_url, identity.source_meeting_url, meeting_id)

    return _IngestMatchIndex(
        by_event_id=by_event_id,
        by_source_meeting_url=by_source_meeting_url,
    )


def _extract_ingest_source_identity(metadata_json: object) -> _IngestSourceIdentity | None:
    if metadata_json is None:
        return None

    try:
        parsed = json.loads(str(metadata_json))
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    raw_source_meeting_url = parsed.get("source_meeting_url")
    raw_selected_event_id = parsed.get("selected_event_id")
    raw_source_url = parsed.get("source_url")

    source_meeting_url = _normalize_url(raw_source_meeting_url)
    if source_meeting_url is None:
        source_meeting_url = _derive_civicclerk_source_meeting_url(
            source_url=_normalize_url(raw_source_url),
            selected_event_id=_normalize_text(raw_selected_event_id),
        )

    return _IngestSourceIdentity(
        selected_event_id=_normalize_text(raw_selected_event_id),
        source_meeting_url=source_meeting_url,
    )


def _resolve_matching_meeting_id(
    *,
    match_index: _IngestMatchIndex,
    discovered_source: object,
) -> str | None:
    source_url = _normalize_url(getattr(discovered_source, "source_url", None))
    source_meeting_id = _normalize_text(getattr(discovered_source, "source_meeting_id", None))

    if source_url is not None:
        meeting_id = match_index.by_source_meeting_url.get(source_url)
        if meeting_id is not None:
            return meeting_id

    if source_meeting_id is not None:
        meeting_id = match_index.by_event_id.get(source_meeting_id)
        if meeting_id is not None:
            return meeting_id

    return None


def _record_unique_match(index: dict[str, str | None], key: str, meeting_id: str) -> None:
    existing = index.get(key)
    if existing is None and key not in index:
        index[key] = meeting_id
        return
    if existing is None:
        return
    if existing != meeting_id:
        index[key] = None


def _derive_civicclerk_source_meeting_url(*, source_url: str | None, selected_event_id: str | None) -> str | None:
    if source_url is None or selected_event_id is None:
        return None

    parsed = urlparse(source_url)
    if not parsed.scheme or not parsed.netloc or not parsed.netloc.endswith("portal.civicclerk.com"):
        return None

    try:
        event_id = int(selected_event_id)
    except ValueError:
        return None

    if event_id <= 0:
        return None

    return f"{parsed.scheme}://{parsed.netloc}/event/{event_id}/files"


def _normalize_text(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_url(value: object) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    if normalized.endswith("/"):
        return normalized.rstrip("/")
    return normalized