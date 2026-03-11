from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from councilsense.app.canonical_persistence import persist_pipeline_canonical_records
from councilsense.app.multi_document_observability import derive_artifact_id, emit_multi_document_stage_event
from councilsense.app.provider_enumeration import ProviderEnumerationError, enumerate_civicclerk_events
from councilsense.app.st031_source_observability import SourceAwareMetricEmitter, emit_source_stage_outcome
from councilsense.db import CityRegistryRepository, MeetingWriteRepository, PILOT_CITY_ID


_DEFAULT_TIMEOUT_SECONDS = 12.0
_DEFAULT_ARTIFACT_ROOT = "/tmp/councilsense-local-latest-artifacts"


class LatestFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class LatestCandidate:
    title: str
    candidate_url: str
    meeting_date_iso: str | None
    score: int
    document_kind: str | None = None


@dataclass(frozen=True)
class LatestFetchResult:
    city_id: str
    source_id: str
    source_url: str
    meeting_id: str
    meeting_uid: str
    fingerprint: str
    artifact_path: str
    candidate_url: str
    candidate_title: str
    candidate_meeting_date: str | None
    candidate_document_kind: str | None
    stage_outcomes: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _CivicClerkDownloadedArtifact:
    document_kind: str
    file_type: str
    file_name: str
    source_url: str
    artifact_bytes: bytes
    artifact_suffix: str
    extracted_text: str


@dataclass(frozen=True)
class _CivicClerkBundleResult:
    candidate: LatestCandidate
    primary_artifact_bytes: bytes
    primary_artifact_suffix: str
    download_warning: str | None
    selected_event_id: int | None
    published_artifacts: tuple[_CivicClerkDownloadedArtifact, ...]


def _normalize_document_kind(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "agenda packet":
        return "packet"
    if normalized in {"minutes", "agenda", "packet"}:
        return normalized
    return None


def _classify_meeting_temporal_status(meeting_date_iso: str | None) -> str | None:
    if not meeting_date_iso:
        return None
    try:
        meeting_date = datetime.fromisoformat(f"{meeting_date_iso}T00:00:00+00:00").date()
    except ValueError:
        return None
    today = datetime.now(tz=UTC).date()
    if meeting_date >= today:
        return "same_day_or_future"
    return "completed"


@dataclass(frozen=True)
class _Anchor:
    href: str
    text: str


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[_Anchor] = []
        self._current_href: str | None = None
        self._current_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = ""
        for name, value in attrs:
            if name.lower() == "href" and value is not None:
                href = value.strip()
                break
        if not href:
            return
        self._current_href = href
        self._current_text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is None:
            return
        if data.strip():
            self._current_text_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        text = " ".join(self._current_text_parts).strip()
        if text:
            self.anchors.append(_Anchor(href=self._current_href, text=text))
        self._current_href = None
        self._current_text_parts = []


def fetch_latest_meeting(
    connection: sqlite3.Connection,
    *,
    city_id: str = PILOT_CITY_ID,
    source_id: str | None = None,
    source_url_override: str | None = None,
    latest_offset: int = 0,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    artifact_root: str | None = None,
    fetch_url: Callable[[str, float], bytes] | None = None,
    metric_emitter: SourceAwareMetricEmitter | None = None,
) -> LatestFetchResult:
    registry = CityRegistryRepository(connection)
    selected_source_id, source_type, source_url = _resolve_source(
        connection=connection,
        registry=registry,
        city_id=city_id,
        source_id=source_id,
    )

    effective_source_url = (
        source_url_override.strip()
        if isinstance(source_url_override, str) and source_url_override.strip()
        else source_url
    )

    timeout = max(timeout_seconds, 1.0)
    candidate_offset = max(latest_offset, 0)
    fetcher = fetch_url or _fetch_url_bytes
    download_warning: str | None = None
    artifact_suffix = ".html"
    civicclerk_bundle: _CivicClerkBundleResult | None = None
    if _is_civicclerk_portal_url(effective_source_url):
        civicclerk_bundle = _fetch_civicclerk_bundle_from_selected_event(
            source_url=effective_source_url,
            preferred_file_type=source_type,
            latest_offset=candidate_offset,
            timeout_seconds=timeout,
            fetch_url=fetcher,
        )
        candidate = civicclerk_bundle.candidate
        artifact_bytes = civicclerk_bundle.primary_artifact_bytes
        artifact_suffix = civicclerk_bundle.primary_artifact_suffix
        download_warning = civicclerk_bundle.download_warning
    else:
        artifact_bytes = fetcher(effective_source_url, timeout)
        html_text = artifact_bytes.decode("utf-8", errors="replace")
        candidate = extract_latest_candidate(
            html=html_text,
            source_url=effective_source_url,
            latest_offset=candidate_offset,
        )
    fingerprint = _build_fingerprint(
        city_id=city_id,
        source_id=selected_source_id,
        candidate=candidate,
    )
    meeting_uid = f"latest-{fingerprint[:24]}"
    meeting_id = f"meeting-{fingerprint[:16]}"
    artifact_path = _persist_artifact(
        city_id=city_id,
        source_id=selected_source_id,
        artifact_root=(artifact_root or os.getenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT") or _DEFAULT_ARTIFACT_ROOT),
        fingerprint=fingerprint,
        artifact_bytes=artifact_bytes,
        artifact_suffix=artifact_suffix,
    )

    meeting = MeetingWriteRepository(connection).upsert_meeting(
        meeting_id=meeting_id,
        meeting_uid=meeting_uid,
        city_id=city_id,
        title=candidate.title,
    )

    if civicclerk_bundle is not None:
        _persist_civicclerk_bundle_documents(
            connection=connection,
            city_id=city_id,
            meeting_id=meeting.id,
            source_id=selected_source_id,
            artifact_root=(artifact_root or os.getenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT") or _DEFAULT_ARTIFACT_ROOT),
            published_artifacts=civicclerk_bundle.published_artifacts,
        )

    stage_outcome = {
        "stage": "ingest",
        "status": "processed",
        "metadata": {
            "source_id": selected_source_id,
            "source_url": effective_source_url,
            "artifact_path": artifact_path,
            "candidate_url": candidate.candidate_url,
            "meeting_date": candidate.meeting_date_iso,
            "candidate_document_kind": candidate.document_kind,
            "meeting_temporal_status": _classify_meeting_temporal_status(candidate.meeting_date_iso),
            "fingerprint": fingerprint,
            **(
                {
                    "selected_event_id": civicclerk_bundle.selected_event_id,
                    "source_meeting_url": _build_civicclerk_event_portal_url(
                        source_url=effective_source_url,
                        event_id=civicclerk_bundle.selected_event_id,
                    ),
                    "published_document_kinds": [item.document_kind for item in civicclerk_bundle.published_artifacts],
                }
                if civicclerk_bundle is not None
                else {}
            ),
        },
    }
    emit_multi_document_stage_event(
        event_name="pipeline_stage_finished",
        stage="ingest",
        outcome="success",
        status="processed",
        city_id=city_id,
        meeting_id=meeting.id,
        run_id=fingerprint,
        source_id=selected_source_id,
        source_type=source_type,
        artifact_id=derive_artifact_id(artifact_path=artifact_path, meeting_id=meeting.id),
        extra_fields={
            "candidate_document_kind": candidate.document_kind or "unknown",
            "meeting_temporal_status": _classify_meeting_temporal_status(candidate.meeting_date_iso) or "unknown",
            "source_url": effective_source_url,
        },
    )
    emit_source_stage_outcome(
        metric_emitter,
        stage="ingest",
        outcome="success",
        city_id=city_id,
        source_type=source_type,
        status="processed",
    )

    warnings: tuple[str, ...] = ()
    warning_items: list[str] = []
    if candidate.meeting_date_iso is None:
        warning_items.append("candidate_meeting_date_not_detected")
    if download_warning is not None:
        warning_items.append(download_warning)
    warnings = tuple(warning_items)

    return LatestFetchResult(
        city_id=city_id,
        source_id=selected_source_id,
        source_url=effective_source_url,
        meeting_id=meeting.id,
        meeting_uid=meeting_uid,
        fingerprint=fingerprint,
        artifact_path=artifact_path,
        candidate_url=candidate.candidate_url,
        candidate_title=candidate.title,
        candidate_meeting_date=candidate.meeting_date_iso,
        candidate_document_kind=candidate.document_kind,
        stage_outcomes=(stage_outcome,),
        warnings=warnings,
    )


def extract_latest_candidate(*, html: str, source_url: str, latest_offset: int = 0) -> LatestCandidate:
    collector = _AnchorCollector()
    collector.feed(html)

    candidates: list[tuple[date, int, str, LatestCandidate]] = []
    for anchor in collector.anchors:
        normalized_url = urljoin(source_url, anchor.href)
        score = _score_candidate(anchor.text, normalized_url)
        if score <= 0:
            continue

        parsed_date = _parse_date_from_text(f"{anchor.text} {normalized_url}")
        normalized_date = parsed_date or date(1970, 1, 1)
        title = _normalize_space(unescape(anchor.text))
        candidate = LatestCandidate(
            title=title,
            candidate_url=normalized_url,
            meeting_date_iso=parsed_date.isoformat() if parsed_date is not None else None,
            score=score,
            document_kind=None,
        )
        candidates.append((normalized_date, score, normalized_url, candidate))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        candidate_index = max(latest_offset, 0)
        if candidate_index >= len(candidates):
            raise LatestFetchError(
                f"Requested latest_offset={candidate_index} but only {len(candidates)} eligible meeting candidates were found"
            )
        return candidates[candidate_index][3]

    fallback_title = _extract_title_tag(html) or "Latest meeting source"
    return LatestCandidate(
        title=_normalize_space(fallback_title),
        candidate_url=source_url,
        meeting_date_iso=None,
        score=0,
        document_kind=None,
    )


def _resolve_source(
    *,
    connection: sqlite3.Connection,
    registry: CityRegistryRepository,
    city_id: str,
    source_id: str | None,
) -> tuple[str, str, str]:
    sources = registry.list_enabled_sources_for_city(city_id)
    if not sources:
        raise LatestFetchError(f"No enabled sources configured for city_id={city_id}")

    if source_id is not None:
        for source in sources:
            if source.id == source_id:
                return (source.id, source.source_type, source.source_url)
        raise LatestFetchError(f"Configured source not found for city_id={city_id}: source_id={source_id}")

    minutes_source = next((source for source in sources if source.source_type == "minutes"), None)
    selected = minutes_source or sources[0]

    existing_city = connection.execute(
        "SELECT 1 FROM cities WHERE id = ? AND enabled = 1",
        (city_id,),
    ).fetchone()
    if existing_city is None:
        raise LatestFetchError(f"Enabled city not found: city_id={city_id}")

    return (selected.id, selected.source_type, selected.source_url)


def _fetch_url_bytes(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "councilsense-local-runtime/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _is_civicclerk_portal_url(source_url: str) -> bool:
    parsed = urlparse(source_url)
    return parsed.netloc.endswith("portal.civicclerk.com")


def _fetch_latest_candidate_from_civicclerk(
    *,
    source_url: str,
    preferred_file_type: str,
    latest_offset: int = 0,
    timeout_seconds: float,
    fetch_url: Callable[[str, float], bytes] | None = None,
) -> tuple[LatestCandidate, bytes, str, str | None]:
    bundle = _fetch_civicclerk_bundle_from_selected_event(
        source_url=source_url,
        preferred_file_type=preferred_file_type,
        latest_offset=latest_offset,
        timeout_seconds=timeout_seconds,
        fetch_url=fetch_url,
    )
    return (
        bundle.candidate,
        bundle.primary_artifact_bytes,
        bundle.primary_artifact_suffix,
        bundle.download_warning,
    )


def _fetch_civicclerk_bundle_from_selected_event(
    *,
    source_url: str,
    preferred_file_type: str,
    latest_offset: int = 0,
    timeout_seconds: float,
    fetch_url: Callable[[str, float], bytes] | None = None,
) -> _CivicClerkBundleResult:
    parsed = urlparse(source_url)
    tenant = parsed.netloc.split(".")[0]
    if not tenant:
        raise LatestFetchError(f"Unable to resolve CivicClerk tenant from source URL: {source_url}")

    api_base_url = f"https://{tenant}.api.civicclerk.com/v1"
    explicit_event_id = _extract_event_id_from_portal_url(source_url)
    events_url = f"{api_base_url}/events?$orderby=eventDate%20desc,id%20desc&$top=200"
    fetcher = fetch_url or _fetch_url_bytes
    selected_event = _select_civicclerk_event(
        api_base_url=api_base_url,
        source_url=source_url,
        events_url=events_url,
        explicit_event_id=explicit_event_id,
        preferred_file_type=preferred_file_type,
        latest_offset=max(latest_offset, 0),
        timeout_seconds=timeout_seconds,
        fetcher=fetcher,
    )

    selected_file = _select_published_file(event=selected_event, preferred_type=preferred_file_type)

    if selected_file is None:
        raise LatestFetchError("No published minutes, agenda, or packet file was found for the latest City Council events")

    event_date_iso = _parse_event_date_iso(selected_event)
    event_name = str(selected_event.get("eventName") or "City Council Meeting")
    file_type = str(selected_file.get("type") or "Agenda")
    file_name = str(selected_file.get("name") or "Published Document")
    file_url_raw = str(selected_file.get("url") or "").strip()
    file_id_value = selected_file.get("fileId")
    file_id: int | None = None
    try:
        if file_id_value is not None:
            file_id = int(str(file_id_value))
    except (TypeError, ValueError):
        file_id = None

    if file_id is not None:
        candidate_url = _resolve_civicclerk_blob_uri(
            api_base_url=api_base_url,
            file_id=file_id,
            plain_text=False,
            timeout_seconds=timeout_seconds,
            fetcher=fetcher,
        )
    elif file_url_raw:
        if file_url_raw.startswith("http://") or file_url_raw.startswith("https://"):
            candidate_url = file_url_raw
        else:
            candidate_url = f"{api_base_url}/{file_url_raw.lstrip('/')}"
    else:
        raise LatestFetchError("Selected CivicClerk event file did not include a fileId or URL")

    candidate_title = _normalize_space(f"{event_name} {event_date_iso or 'unknown-date'} {file_type} {file_name}")
    candidate = LatestCandidate(
        title=candidate_title,
        candidate_url=candidate_url,
        meeting_date_iso=event_date_iso,
        score=10,
        document_kind=_normalize_document_kind(file_type),
    )

    primary_artifact, download_warning = _download_civicclerk_published_artifact(
        api_base_url=api_base_url,
        selected_event=selected_event,
        published_file=selected_file,
        timeout_seconds=timeout_seconds,
        fetcher=fetcher,
    )

    published_artifacts: list[_CivicClerkDownloadedArtifact] = [primary_artifact]
    seen_document_kinds = {primary_artifact.document_kind}
    for item in _list_supported_published_files(selected_event):
        if not isinstance(item, dict):
            continue
        document_kind = _normalize_document_kind(str(item.get("type") or ""))
        if document_kind is None or document_kind in seen_document_kinds:
            continue
        artifact, artifact_warning = _download_civicclerk_published_artifact(
            api_base_url=api_base_url,
            selected_event=selected_event,
            published_file=item,
            timeout_seconds=timeout_seconds,
            fetcher=fetcher,
        )
        if artifact_warning is not None and not artifact.extracted_text:
            continue
        published_artifacts.append(artifact)
        seen_document_kinds.add(document_kind)

    selected_event_id: int | None = None
    try:
        if selected_event.get("id") is not None:
            selected_event_id = int(str(selected_event.get("id")))
    except (TypeError, ValueError):
        selected_event_id = None

    return _CivicClerkBundleResult(
        candidate=candidate,
        primary_artifact_bytes=primary_artifact.artifact_bytes,
        primary_artifact_suffix=primary_artifact.artifact_suffix,
        download_warning=download_warning,
        selected_event_id=selected_event_id,
        published_artifacts=tuple(published_artifacts),
    )


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


def _download_civicclerk_published_artifact(
    *,
    api_base_url: str,
    selected_event: dict[str, object],
    published_file: dict[str, object],
    timeout_seconds: float,
    fetcher: Callable[[str, float], bytes],
) -> tuple[_CivicClerkDownloadedArtifact, str | None]:
    file_type = str(published_file.get("type") or "Agenda")
    document_kind = _normalize_document_kind(file_type)
    if document_kind is None:
        raise LatestFetchError(f"Unsupported CivicClerk published file type: {file_type}")

    file_name = str(published_file.get("name") or "Published Document")
    file_url_raw = str(published_file.get("url") or "").strip()
    file_id_value = published_file.get("fileId")
    file_id: int | None = None
    try:
        if file_id_value is not None:
            file_id = int(str(file_id_value))
    except (TypeError, ValueError):
        file_id = None

    if file_id is not None:
        candidate_url = _resolve_civicclerk_blob_uri(
            api_base_url=api_base_url,
            file_id=file_id,
            plain_text=False,
            timeout_seconds=timeout_seconds,
            fetcher=fetcher,
        )
    elif file_url_raw:
        if file_url_raw.startswith("http://") or file_url_raw.startswith("https://"):
            candidate_url = file_url_raw
        else:
            candidate_url = f"{api_base_url}/{file_url_raw.lstrip('/')}"
    else:
        raise LatestFetchError("Selected CivicClerk event file did not include a fileId or URL")

    if file_id is not None:
        try:
            plain_text_url = _resolve_civicclerk_blob_uri(
                api_base_url=api_base_url,
                file_id=file_id,
                plain_text=True,
                timeout_seconds=timeout_seconds,
                fetcher=fetcher,
            )
            plain_text_bytes = fetcher(plain_text_url, timeout_seconds)
            if plain_text_bytes.strip():
                return (
                    _CivicClerkDownloadedArtifact(
                        document_kind=document_kind,
                        file_type=file_type,
                        file_name=file_name,
                        source_url=plain_text_url,
                        artifact_bytes=plain_text_bytes,
                        artifact_suffix=".txt",
                        extracted_text=_extract_text_from_downloaded_artifact(plain_text_bytes, ".txt"),
                    ),
                    None,
                )
        except Exception:
            pass

    try:
        document_bytes = fetcher(candidate_url, timeout_seconds)
        suffix = _infer_artifact_suffix(candidate_url=candidate_url, content_bytes=document_bytes)
        return (
            _CivicClerkDownloadedArtifact(
                document_kind=document_kind,
                file_type=file_type,
                file_name=file_name,
                source_url=candidate_url,
                artifact_bytes=document_bytes,
                artifact_suffix=suffix,
                extracted_text=_extract_text_from_downloaded_artifact(document_bytes, suffix),
            ),
            None,
        )
    except Exception:
        metadata_bytes = json.dumps(
            {
                "source": "civicclerk_events",
                "selected_event_id": selected_event.get("id"),
                "selected_event_name": selected_event.get("eventName"),
                "selected_event_date": _parse_event_date_iso(selected_event),
                "selected_file": published_file,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return (
            _CivicClerkDownloadedArtifact(
                document_kind=document_kind,
                file_type=file_type,
                file_name=file_name,
                source_url=candidate_url,
                artifact_bytes=metadata_bytes,
                artifact_suffix=".json",
                extracted_text="",
            ),
            "candidate_document_download_failed",
        )


def _extract_text_from_downloaded_artifact(artifact_bytes: bytes, artifact_suffix: str) -> str:
    normalized_suffix = artifact_suffix.lower()
    if normalized_suffix == ".pdf" or artifact_bytes.startswith(b"%PDF"):
        try:
            from pypdf import PdfReader
        except Exception:
            return ""

        try:
            reader = PdfReader(BytesIO(artifact_bytes))
        except Exception:
            return ""

        parts: list[str] = []
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            normalized = _normalize_space(page_text)
            if normalized:
                parts.append(normalized)
        return " ".join(parts).strip()

    return _normalize_space(artifact_bytes.decode("utf-8", errors="replace"))


def _persist_civicclerk_bundle_documents(
    *,
    connection: sqlite3.Connection,
    city_id: str,
    meeting_id: str,
    source_id: str,
    artifact_root: str,
    published_artifacts: tuple[_CivicClerkDownloadedArtifact, ...],
) -> None:
    for artifact in published_artifacts:
        artifact_path = _persist_artifact(
            city_id=city_id,
            source_id=f"{source_id}-{artifact.document_kind}",
            artifact_root=artifact_root,
            fingerprint=_build_civicclerk_bundle_artifact_fingerprint(
                city_id=city_id,
                meeting_id=meeting_id,
                document_kind=artifact.document_kind,
                source_url=artifact.source_url,
            ),
            artifact_bytes=artifact.artifact_bytes,
            artifact_suffix=artifact.artifact_suffix,
        )
        persist_pipeline_canonical_records(
            connection,
            meeting_id=meeting_id,
            source_id=source_id,
            source_url=artifact.source_url,
            source_type_override=artifact.document_kind,
            extracted_text=(artifact.extracted_text or artifact.file_name),
            extraction_status=("processed" if artifact.extracted_text else "limited_confidence"),
            extraction_confidence=(0.92 if artifact.extracted_text else 0.55),
            artifact_storage_uri=artifact_path,
            evidence_spans=(),
        )


def _build_civicclerk_bundle_artifact_fingerprint(
    *,
    city_id: str,
    meeting_id: str,
    document_kind: str,
    source_url: str,
) -> str:
    return hashlib.sha256(
        "|".join((city_id.strip(), meeting_id.strip(), document_kind.strip(), source_url.strip().lower())).encode(
            "utf-8"
        )
    ).hexdigest()


def _is_city_council_event(event: object) -> bool:
    if not isinstance(event, dict):
        return False
    event_name = str(event.get("eventName") or "").lower()
    return "city council" in event_name


def _event_sort_key(event: dict[str, object]) -> tuple[str, int]:
    date_value = str(event.get("eventDate") or event.get("startDateTime") or "")
    event_id = int(str(event.get("id") or 0))
    return (date_value, event_id)


def _select_published_file(*, event: dict[str, object], preferred_type: str) -> dict[str, object] | None:
    published_files = event.get("publishedFiles")
    if not isinstance(published_files, list):
        return None

    preferred = preferred_type.strip().lower()
    preferred_aliases = _preferred_type_aliases(preferred)
    for alias in preferred_aliases:
        for item in published_files:
            if not isinstance(item, dict):
                continue
            file_type = str(item.get("type") or "").strip().lower()
            if file_type == alias:
                return item

    if preferred:
        return None

    for item in published_files:
        if not isinstance(item, dict):
            continue
        file_type = str(item.get("type") or "").strip().lower()
        if file_type in {"minutes", "agenda", "agenda packet", "packet"}:
            return item
    return None


def _has_preferred_published_file(*, event: dict[str, object], preferred_type: str) -> bool:
    published_files = event.get("publishedFiles")
    if not isinstance(published_files, list):
        return False

    preferred = preferred_type.strip().lower()
    if not preferred:
        return False

    preferred_aliases = set(_preferred_type_aliases(preferred))
    for item in published_files:
        if not isinstance(item, dict):
            continue
        file_type = str(item.get("type") or "").strip().lower()
        if file_type in preferred_aliases:
            return True
    return False


def _preferred_type_aliases(preferred_type: str) -> tuple[str, ...]:
    if preferred_type == "minutes":
        return ("minutes",)
    if preferred_type == "agenda":
        return ("agenda",)
    if preferred_type == "packet":
        return ("agenda packet", "packet")
    return (preferred_type,)


def _extract_event_id_from_portal_url(source_url: str) -> int | None:
    match = re.search(r"/event/(\d+)(?:/|$)", source_url)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _build_civicclerk_event_portal_url(*, source_url: str, event_id: int | None) -> str | None:
    if event_id is None or event_id <= 0:
        return None

    parsed = urlparse(source_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}/event/{event_id}/files"


def _select_civicclerk_event(
    *,
    api_base_url: str,
    source_url: str,
    events_url: str,
    explicit_event_id: int | None,
    preferred_file_type: str,
    latest_offset: int,
    timeout_seconds: float,
    fetcher: Callable[[str, float], bytes],
) -> dict[str, object]:
    if explicit_event_id is not None and latest_offset == 0:
        event = _fetch_civicclerk_event_by_id(
            api_base_url=api_base_url,
            event_id=explicit_event_id,
            timeout_seconds=timeout_seconds,
            fetcher=fetcher,
        )
        if event is not None:
            return event

    try:
        council_events = [
            dict(item.raw_payload)
            for item in enumerate_civicclerk_events(
                source_url=source_url,
                timeout_seconds=timeout_seconds,
                fetch_url=fetcher,
            )
        ]
    except ProviderEnumerationError as exc:
        raise LatestFetchError(str(exc)) from exc

    normalized_preferred_type = preferred_file_type.strip().lower()
    today_iso = datetime.now(tz=UTC).date().isoformat()

    council_events.sort(key=_event_sort_key, reverse=True)

    with_preferred_files = [
        event
        for event in council_events
        if _has_preferred_published_file(event=event, preferred_type=normalized_preferred_type)
    ]
    completed_with_preferred = [
        event
        for event in with_preferred_files
        if _event_sort_key(event)[0] and _event_sort_key(event)[0] <= today_iso
    ]

    if completed_with_preferred:
        completed_with_preferred.sort(key=_event_sort_key, reverse=True)
        return _select_offset_event(completed_with_preferred, latest_offset=latest_offset)

    if with_preferred_files:
        return _select_offset_event(with_preferred_files, latest_offset=latest_offset)

    with_any_supported_file = [
        event
        for event in council_events
        if _select_published_file(event=event, preferred_type="") is not None
    ]
    completed_with_any_supported_file = [
        event
        for event in with_any_supported_file
        if _event_sort_key(event)[0] and _event_sort_key(event)[0] <= today_iso
    ]

    if completed_with_any_supported_file:
        completed_with_any_supported_file.sort(key=_event_sort_key, reverse=True)
        return _select_offset_event(completed_with_any_supported_file, latest_offset=latest_offset)

    if with_any_supported_file:
        return _select_offset_event(with_any_supported_file, latest_offset=latest_offset)

    return _select_offset_event(council_events, latest_offset=latest_offset)


def _select_offset_event(
    events: list[dict[str, object]],
    *,
    latest_offset: int,
) -> dict[str, object]:
    if latest_offset >= len(events):
        raise LatestFetchError(
            f"Requested latest_offset={latest_offset} but only {len(events)} eligible CivicClerk events were found"
        )
    return events[latest_offset]


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
    for raw in matches:
        try:
            event_id = int(raw)
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
    event_url = f"{api_base_url}/Events/{event_id}"
    try:
        raw = fetcher(event_url, timeout_seconds)
    except Exception:
        return None
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
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
    agenda_id_value = event.get("agendaId")
    meeting_id: int | None = None
    try:
        if agenda_id_value is not None:
            meeting_id = int(str(agenda_id_value))
    except (TypeError, ValueError):
        meeting_id = None

    if meeting_id is None or meeting_id <= 0:
        return event

    meeting_url = f"{api_base_url}/Meetings/{meeting_id}"
    try:
        raw = fetcher(meeting_url, timeout_seconds)
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


def _parse_event_date_iso(event: dict[str, object]) -> str | None:
    raw = str(event.get("eventDate") or event.get("startDateTime") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        return None


def _persist_artifact(
    *,
    city_id: str,
    source_id: str,
    artifact_root: str,
    fingerprint: str,
    artifact_bytes: bytes,
    artifact_suffix: str,
) -> str:
    artifact_dir = Path(artifact_root) / city_id / source_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    normalized_suffix = artifact_suffix if artifact_suffix.startswith(".") else f".{artifact_suffix}"
    artifact_path = artifact_dir / f"{fingerprint}{normalized_suffix}"
    artifact_path.write_bytes(artifact_bytes)
    return str(artifact_path)


def _infer_artifact_suffix(*, candidate_url: str, content_bytes: bytes) -> str:
    parsed = urlparse(candidate_url)
    ext = Path(parsed.path).suffix.lower()
    if ext in {".pdf", ".txt", ".html", ".htm", ".json"}:
        return ext
    if content_bytes.startswith(b"%PDF"):
        return ".pdf"
    if content_bytes.lstrip().startswith((b"{", b"[")):
        return ".json"
    return ".bin"


def _resolve_civicclerk_blob_uri(
    *,
    api_base_url: str,
    file_id: int,
    plain_text: bool,
    timeout_seconds: float,
    fetcher: Callable[[str, float], bytes],
) -> str:
    endpoint = (
        f"{api_base_url}/Meetings/GetMeetingFile"
        f"(fileId={file_id},plainText={'true' if plain_text else 'false'})"
    )
    raw = fetcher(endpoint, timeout_seconds)
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise LatestFetchError("CivicClerk GetMeetingFile response was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise LatestFetchError("CivicClerk GetMeetingFile response was not an object")
    blob_uri = str(payload.get("blobUri") or "").strip()
    if not blob_uri:
        raise LatestFetchError("CivicClerk GetMeetingFile response did not include blobUri")
    return blob_uri


def _build_fingerprint(*, city_id: str, source_id: str, candidate: LatestCandidate) -> str:
    digest_input = "|".join(
        (
            city_id.strip(),
            source_id.strip(),
            candidate.candidate_url.strip().lower(),
            (candidate.meeting_date_iso or "unknown-date"),
            _normalize_space(candidate.title).lower(),
        )
    )
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def _score_candidate(text: str, url: str) -> int:
    haystack = f"{text} {url}".lower()
    score = 0
    if "minute" in haystack or "agenda" in haystack:
        score += 3
    if "council" in haystack or "meeting" in haystack:
        score += 2
    if any(token in haystack for token in ("/agenda", "/minutes", "agenda-center", ".pdf", ".doc")):
        score += 2
    if _parse_date_from_text(haystack) is not None:
        score += 4
    return score


def _extract_title_tag(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return None
    return _normalize_space(unescape(match.group(1)))


def _parse_date_from_text(value: str) -> date | None:
    mmddyyyy_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", value)
    if mmddyyyy_match is not None:
        try:
            month, day, year = (int(mmddyyyy_match.group(1)), int(mmddyyyy_match.group(2)), int(mmddyyyy_match.group(3)))
            return date(year, month, day)
        except ValueError:
            pass

    yyyymmdd_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", value)
    if yyyymmdd_match is not None:
        try:
            year, month, day = (
                int(yyyymmdd_match.group(1)),
                int(yyyymmdd_match.group(2)),
                int(yyyymmdd_match.group(3)),
            )
            return date(year, month, day)
        except ValueError:
            pass

    month_name_match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})\b",
        value,
        flags=re.IGNORECASE,
    )
    if month_name_match is not None:
        try:
            parsed = datetime.strptime(month_name_match.group(0), "%B %d, %Y").replace(tzinfo=UTC)
            return parsed.date()
        except ValueError:
            return None

    return None


def _normalize_space(value: str) -> str:
    return " ".join(value.split())
