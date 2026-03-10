from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Protocol
from urllib.parse import urlparse

from councilsense.db.city_registry import CitySourceConfig
from councilsense.db.discovered_meetings import DiscoveredMeetingIdentity


class ProviderEnumerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CivicClerkEnumeratedEvent:
    source_meeting_id: str
    title: str
    meeting_date: str | None
    body_name: str | None
    source_url: str
    provider_metadata: dict[str, object]
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class EnumeratedMeeting:
    identity: DiscoveredMeetingIdentity
    title: str
    meeting_date: str | None
    body_name: str | None
    source_url: str
    provider_metadata: dict[str, object]
    raw_payload: dict[str, object]


class SourceMeetingEnumerationProvider(Protocol):
    provider_name: str

    def supports_source(self, source: CitySourceConfig) -> bool:
        ...

    def enumerate_meetings(
        self,
        *,
        source: CitySourceConfig,
        timeout_seconds: float,
        fetch_url: Callable[[str, float], bytes],
    ) -> tuple[EnumeratedMeeting, ...]:
        ...


class CivicClerkSourceMeetingEnumerationProvider:
    provider_name = "civicclerk"

    def supports_source(self, source: CitySourceConfig) -> bool:
        parser_name = source.parser_name.strip().lower()
        return parser_name.startswith("civicclerk") or _is_civicclerk_portal_url(source.source_url)

    def enumerate_meetings(
        self,
        *,
        source: CitySourceConfig,
        timeout_seconds: float,
        fetch_url: Callable[[str, float], bytes],
    ) -> tuple[EnumeratedMeeting, ...]:
        events = enumerate_civicclerk_events(
            source_url=source.source_url,
            timeout_seconds=timeout_seconds,
            fetch_url=fetch_url,
        )
        return tuple(
            EnumeratedMeeting(
                identity=DiscoveredMeetingIdentity(
                    city_id=source.city_id,
                    city_source_id=source.id,
                    provider_name=self.provider_name,
                    source_meeting_id=event.source_meeting_id,
                ),
                title=event.title,
                meeting_date=event.meeting_date,
                body_name=event.body_name,
                source_url=event.source_url,
                provider_metadata=dict(event.provider_metadata),
                raw_payload=dict(event.raw_payload),
            )
            for event in events
        )


def get_source_meeting_enumeration_provider(source: CitySourceConfig) -> SourceMeetingEnumerationProvider:
    provider = CivicClerkSourceMeetingEnumerationProvider()
    if provider.supports_source(source):
        return provider
    raise ProviderEnumerationError(f"No source enumeration provider is configured for source_id={source.id}")


def enumerate_civicclerk_events(
    *,
    source_url: str,
    timeout_seconds: float,
    fetch_url: Callable[[str, float], bytes],
) -> tuple[CivicClerkEnumeratedEvent, ...]:
    api_base_url = _build_civicclerk_api_base_url(source_url)
    fallback_events_url = f"{api_base_url}/events?$orderby=eventDate%20desc,id%20desc&$top=200"
    feed_urls = _build_civicclerk_events_feed_urls(
        api_base_url=api_base_url,
        fallback_events_url=fallback_events_url,
    )

    enriched_events: list[dict[str, object]] = []
    for feed_url in feed_urls:
        try:
            raw = fetch_url(feed_url, timeout_seconds)
            payload = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue

        items = payload.get("value") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            continue
        enriched_events.extend(
            _enrich_civicclerk_event(
                event=item,
                api_base_url=api_base_url,
                timeout_seconds=timeout_seconds,
                fetcher=fetch_url,
            )
            for item in items
            if isinstance(item, dict)
        )

    known_ids: set[int] = set()
    for event in enriched_events:
        event_id = _parse_event_id(event.get("id"))
        if event_id is not None:
            known_ids.add(event_id)

    for event_id in _fetch_event_ids_from_portal(
        source_url=source_url,
        timeout_seconds=timeout_seconds,
        fetcher=fetch_url,
    ):
        if event_id in known_ids:
            continue
        event = _fetch_civicclerk_event_by_id(
            api_base_url=api_base_url,
            event_id=event_id,
            timeout_seconds=timeout_seconds,
            fetcher=fetch_url,
        )
        if event is None:
            continue
        enriched_events.append(event)
        known_ids.add(event_id)

    council_events = [event for event in enriched_events if _is_city_council_event(event)]
    if not council_events:
        raise ProviderEnumerationError("No City Council events were found in CivicClerk events payload")

    deduped: dict[str, CivicClerkEnumeratedEvent] = {}
    for event in council_events:
        normalized = _normalize_civicclerk_event(source_url=source_url, event=event)
        if normalized is None:
            continue
        existing = deduped.get(normalized.source_meeting_id)
        if existing is None or _civicclerk_event_rank(normalized) > _civicclerk_event_rank(existing):
            deduped[normalized.source_meeting_id] = normalized

    if not deduped:
        raise ProviderEnumerationError("No CivicClerk events produced a stable source identity")

    ordered = sorted(deduped.values(), key=_civicclerk_enumerated_sort_key, reverse=True)
    return tuple(ordered)


def _normalize_civicclerk_event(
    *,
    source_url: str,
    event: dict[str, object],
) -> CivicClerkEnumeratedEvent | None:
    event_id = _parse_event_id(event.get("id"))
    if event_id is None:
        return None

    event_name = _normalize_space(str(event.get("eventName") or ""))
    meeting_date = _parse_event_date_iso(event)
    published_document_kinds = tuple(
        document_kind
        for document_kind in (
            _normalize_document_kind(str(item.get("type") or ""))
            for item in _list_supported_published_files(event)
        )
        if document_kind is not None
    )
    portal_url = _build_civicclerk_event_portal_url(source_url=source_url, event_id=event_id) or source_url

    return CivicClerkEnumeratedEvent(
        source_meeting_id=str(event_id),
        title=event_name or f"CivicClerk Event {event_id}",
        meeting_date=meeting_date,
        body_name=_derive_civicclerk_body_name(event_name),
        source_url=portal_url,
        provider_metadata={
            "selected_event_id": event_id,
            "event_name": event_name or None,
            "published_document_kinds": published_document_kinds,
        },
        raw_payload=dict(event),
    )


def _civicclerk_event_rank(event: CivicClerkEnumeratedEvent) -> tuple[int, int, int, str, int]:
    published_document_kinds = event.provider_metadata.get("published_document_kinds")
    published_count = len(published_document_kinds) if isinstance(published_document_kinds, tuple) else 0
    body_name = event.body_name or ""
    raw_event_id = _parse_event_id(event.raw_payload.get("id")) or 0
    return (
        published_count,
        1 if event.meeting_date else 0,
        len(body_name),
        event.title,
        raw_event_id,
    )


def _civicclerk_enumerated_sort_key(event: CivicClerkEnumeratedEvent) -> tuple[str, int]:
    return (_event_sort_key(event.raw_payload)[0], _parse_event_id(event.raw_payload.get("id")) or 0)


def _derive_civicclerk_body_name(event_name: str) -> str | None:
    if not event_name:
        return None
    lowered = event_name.lower()
    if "city council" in lowered:
        return "City Council"
    return event_name


def _is_civicclerk_portal_url(source_url: str) -> bool:
    parsed = urlparse(source_url)
    return parsed.netloc.endswith("portal.civicclerk.com")


def _build_civicclerk_api_base_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    tenant = parsed.netloc.split(".")[0]
    if not tenant:
        raise ProviderEnumerationError(f"Unable to resolve CivicClerk tenant from source URL: {source_url}")
    return f"https://{tenant}.api.civicclerk.com/v1"


def _is_city_council_event(event: object) -> bool:
    if not isinstance(event, dict):
        return False
    event_name = str(event.get("eventName") or "").lower()
    return "city council" in event_name


def _event_sort_key(event: dict[str, object]) -> tuple[str, int]:
    date_value = str(event.get("eventDate") or event.get("startDateTime") or "")
    return (date_value, _parse_event_id(event.get("id")) or 0)


def _build_civicclerk_events_feed_urls(*, api_base_url: str, fallback_events_url: str) -> tuple[str, ...]:
    today_iso = datetime.now(tz=UTC).date().isoformat()
    return (
        f"{api_base_url}/Events?$filter=startDateTime+lt+{today_iso}&$orderby=startDateTime+desc,+eventName+desc",
        f"{api_base_url}/Events?$filter=startDateTime+ge+{today_iso}&$orderby=startDateTime+asc,+eventName+asc",
        fallback_events_url,
    )


def _fetch_event_ids_from_portal(
    *,
    source_url: str,
    timeout_seconds: float,
    fetcher: Callable[[str, float], bytes],
) -> tuple[int, ...]:
    try:
        raw = fetcher(source_url, timeout_seconds)
        html = raw.decode("utf-8", errors="replace")
    except Exception:
        return ()
    return _extract_event_ids_from_html(html)


def _extract_event_ids_from_html(html: str) -> tuple[int, ...]:
    matches = re.findall(r"/event/(\d+)/files", html, flags=re.IGNORECASE)
    seen: set[int] = set()
    ids: list[int] = []
    for raw_id in matches:
        try:
            event_id = int(raw_id)
        except ValueError:
            continue
        if event_id in seen:
            continue
        seen.add(event_id)
        ids.append(event_id)
        if len(ids) >= 40:
            break
    return tuple(ids)


def _fetch_civicclerk_event_by_id(
    *,
    api_base_url: str,
    event_id: int,
    timeout_seconds: float,
    fetcher: Callable[[str, float], bytes],
) -> dict[str, object] | None:
    try:
        raw = fetcher(f"{api_base_url}/Events/{event_id}", timeout_seconds)
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return _enrich_civicclerk_event(
        event=payload,
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        fetcher=fetcher,
    )


def _enrich_civicclerk_event(
    *,
    event: dict[str, object],
    api_base_url: str,
    timeout_seconds: float,
    fetcher: Callable[[str, float], bytes],
) -> dict[str, object]:
    agenda_id = _parse_event_id(event.get("agendaId"))
    if agenda_id is None or agenda_id <= 0:
        return event

    try:
        raw = fetcher(f"{api_base_url}/Meetings/{agenda_id}", timeout_seconds)
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return event
    if not isinstance(payload, dict):
        return event

    published_files = payload.get("publishedFiles")
    if not isinstance(published_files, list):
        return event

    enriched = dict(event)
    enriched["publishedFiles"] = published_files
    return enriched


def _list_supported_published_files(event: dict[str, object]) -> tuple[dict[str, object], ...]:
    published_files = event.get("publishedFiles")
    if not isinstance(published_files, list):
        return ()

    supported: list[dict[str, object]] = []
    seen_document_kinds: set[str] = set()
    for item in published_files:
        if not isinstance(item, dict):
            continue
        document_kind = _normalize_document_kind(str(item.get("type") or ""))
        if document_kind is None or document_kind in seen_document_kinds:
            continue
        supported.append(item)
        seen_document_kinds.add(document_kind)
    return tuple(supported)


def _normalize_document_kind(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "agenda packet":
        return "packet"
    if normalized in {"minutes", "agenda", "packet"}:
        return normalized
    return None


def _parse_event_date_iso(event: dict[str, object]) -> str | None:
    raw = str(event.get("eventDate") or event.get("startDateTime") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.date().isoformat()


def _build_civicclerk_event_portal_url(*, source_url: str, event_id: int | None) -> str | None:
    if event_id is None or event_id <= 0:
        return None
    parsed = urlparse(source_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/event/{event_id}/files"


def _parse_event_id(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()