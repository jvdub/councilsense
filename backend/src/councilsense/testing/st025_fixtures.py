from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from councilsense.app.meeting_bundle_planner import EXPECTED_SOURCE_TYPES
from councilsense.app.multi_document_compose import SummarizeComposeInput, assemble_summarize_compose_input
from councilsense.db import CanonicalDocumentRepository, DocumentKind, PILOT_CITY_ID, apply_migrations, seed_city_registry


ST025_FIXTURE_SCHEMA_VERSION = "st025-source-conflict-partial-coverage-fixtures-v1"


@dataclass(frozen=True)
class St025FixtureSpan:
    stable_section_path: str
    text: str
    precision: str
    confidence: str
    signal_tags: tuple[str, ...]


@dataclass(frozen=True)
class St025FixtureDocument:
    document_id: str
    document_kind: DocumentKind
    revision_id: str
    revision_number: int
    is_active_revision: bool
    extracted_at: str
    authority_level: str
    authority_source: str
    authority_note: str | None
    spans: tuple[St025FixtureSpan, ...]


@dataclass(frozen=True)
class St025ExpectedCompose:
    source_order: tuple[str, ...]
    source_statuses: dict[str, str]
    missing_source_types: tuple[str, ...]
    partial_source_types: tuple[str, ...]
    available_source_types: tuple[str, ...]
    fallback_source_type: str | None
    fallback_text: str


@dataclass(frozen=True)
class St025ExpectedPolicy:
    authority_outcome: str
    publication_status: str
    confidence_reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class St025FixtureScenario:
    fixture_id: str
    scenario_group: str
    description: str
    meeting_id: str
    meeting_uid: str
    meeting_datetime_utc: str
    documents: tuple[St025FixtureDocument, ...]
    expected_compose: St025ExpectedCompose
    expected_policy: St025ExpectedPolicy

    @property
    def stable_fixture_key(self) -> str:
        payload = {
            "fixture_id": self.fixture_id,
            "meeting_id": self.meeting_id,
            "meeting_datetime_utc": self.meeting_datetime_utc,
            "expected_compose": {
                "source_statuses": self.expected_compose.source_statuses,
                "fallback_source_type": self.expected_compose.fallback_source_type,
                "fallback_text": self.expected_compose.fallback_text,
            },
            "expected_policy": {
                "authority_outcome": self.expected_policy.authority_outcome,
                "publication_status": self.expected_policy.publication_status,
                "confidence_reason_codes": list(self.expected_policy.confidence_reason_codes),
            },
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return f"st025-{digest[:16]}"


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "st025_source_conflict_and_partial_coverage_fixtures.json"


def create_test_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)
    return connection


def load_fixture_catalog(*, manifest_path: Path | None = None) -> tuple[St025FixtureScenario, ...]:
    resolved_manifest_path = manifest_path or default_manifest_path()
    payload = cast(dict[str, Any], json.loads(resolved_manifest_path.read_text(encoding="utf-8")))
    if payload.get("schema_version") != ST025_FIXTURE_SCHEMA_VERSION:
        raise ValueError(
            f"ST-025 fixture catalog must declare schema_version={ST025_FIXTURE_SCHEMA_VERSION}."
        )

    raw_fixtures = payload.get("fixtures")
    if not isinstance(raw_fixtures, list):
        raise ValueError("ST-025 fixture catalog must include a list at 'fixtures'.")

    fixtures: list[St025FixtureScenario] = []
    for raw_fixture in raw_fixtures:
        if not isinstance(raw_fixture, dict):
            raise ValueError("ST-025 fixture entries must be objects.")
        fixtures.append(_parse_fixture(raw_fixture))

    fixture_ids = [fixture.fixture_id for fixture in fixtures]
    if len(set(fixture_ids)) != len(fixture_ids):
        raise ValueError("ST-025 fixture catalog contains duplicate fixture_id values.")

    meeting_ids = [fixture.meeting_id for fixture in fixtures]
    if len(set(meeting_ids)) != len(meeting_ids):
        raise ValueError("ST-025 fixture catalog contains duplicate meeting_id values.")

    required_groups = {"source_conflict", "partial_coverage", "weak_precision"}
    seen_groups = {fixture.scenario_group for fixture in fixtures}
    if seen_groups != required_groups:
        raise ValueError(
            "ST-025 fixture catalog must cover source_conflict, partial_coverage, and weak_precision groups."
        )

    for fixture in fixtures:
        _validate_fixture(fixture)

    return tuple(sorted(fixtures, key=lambda fixture: fixture.fixture_id))


def seed_fixture_scenario(*, connection: sqlite3.Connection, scenario: St025FixtureScenario) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (scenario.meeting_id, PILOT_CITY_ID, scenario.meeting_uid, f"ST025 Fixture {scenario.fixture_id}"),
    )

    repository = CanonicalDocumentRepository(connection)
    for document in scenario.documents:
        record = repository.upsert_document_revision(
            canonical_document_id=document.document_id,
            meeting_id=scenario.meeting_id,
            document_kind=document.document_kind,
            revision_id=document.revision_id,
            revision_number=document.revision_number,
            is_active_revision=document.is_active_revision,
            authority_level=document.authority_level,
            authority_source=document.authority_source,
            authority_note=document.authority_note,
            source_document_url=f"https://example.org/{scenario.fixture_id}/{document.document_kind}/{document.revision_id}",
            source_checksum=f"sha256:{scenario.fixture_id}:{document.document_kind}:{document.revision_id}",
            parser_name="fixture-parser",
            parser_version="st025-fixtures-v1",
            extraction_status="processed",
            extraction_confidence=0.9,
            extracted_at=document.extracted_at,
        )
        for index, span in enumerate(document.spans, start=1):
            repository.upsert_document_span(
                canonical_document_span_id=f"span-{record.id}-{index}",
                canonical_document_id=record.id,
                artifact_id=f"artifact-normalized-{record.id}",
                stable_section_path=span.stable_section_path,
                page_number=None,
                line_index=index,
                start_char_offset=0,
                end_char_offset=len(span.text),
                parser_name="fixture-parser",
                parser_version="st025-fixtures-v1",
                source_chunk_id=f"chunk-{index}",
                span_text=span.text,
                span_text_checksum=f"sha256:{scenario.fixture_id}:{document.document_kind}:{index}",
            )


def assemble_fixture_compose(
    *,
    connection: sqlite3.Connection,
    scenario: St025FixtureScenario,
) -> SummarizeComposeInput:
    return assemble_summarize_compose_input(
        connection=connection,
        meeting_id=scenario.meeting_id,
        fallback_source_type=scenario.expected_compose.fallback_source_type,
        fallback_text=scenario.expected_compose.fallback_text,
    )


def collect_precision_signal_tags(*, scenario: St025FixtureScenario) -> tuple[str, ...]:
    tags = {
        tag
        for document in scenario.documents
        for span in document.spans
        for tag in span.signal_tags
        if tag.strip()
    }
    return tuple(sorted(tags))


def _parse_fixture(raw_fixture: dict[str, Any]) -> St025FixtureScenario:
    raw_expected_compose = cast(dict[str, Any], raw_fixture.get("expected_compose") or {})
    raw_expected_policy = cast(dict[str, Any], raw_fixture.get("expected_policy") or {})
    raw_documents = raw_fixture.get("documents") or []
    if not isinstance(raw_documents, list):
        raise ValueError("ST-025 fixture documents must be a list.")

    documents = tuple(_parse_document(raw_document) for raw_document in raw_documents)

    return St025FixtureScenario(
        fixture_id=str(raw_fixture.get("fixture_id") or "").strip(),
        scenario_group=str(raw_fixture.get("scenario_group") or "").strip(),
        description=str(raw_fixture.get("description") or "").strip(),
        meeting_id=str(raw_fixture.get("meeting_id") or "").strip(),
        meeting_uid=str(raw_fixture.get("meeting_uid") or "").strip(),
        meeting_datetime_utc=str(raw_fixture.get("meeting_datetime_utc") or "").strip(),
        documents=documents,
        expected_compose=St025ExpectedCompose(
            source_order=tuple(str(item).strip() for item in raw_expected_compose.get("source_order") or ()),
            source_statuses={
                str(key).strip(): str(value).strip()
                for key, value in cast(dict[str, Any], raw_expected_compose.get("source_statuses") or {}).items()
            },
            missing_source_types=tuple(str(item).strip() for item in raw_expected_compose.get("missing_source_types") or ()),
            partial_source_types=tuple(str(item).strip() for item in raw_expected_compose.get("partial_source_types") or ()),
            available_source_types=tuple(str(item).strip() for item in raw_expected_compose.get("available_source_types") or ()),
            fallback_source_type=(
                str(raw_expected_compose.get("fallback_source_type")).strip()
                if raw_expected_compose.get("fallback_source_type") is not None
                else None
            ),
            fallback_text=str(raw_expected_compose.get("fallback_text") or "").strip(),
        ),
        expected_policy=St025ExpectedPolicy(
            authority_outcome=str(raw_expected_policy.get("authority_outcome") or "").strip(),
            publication_status=str(raw_expected_policy.get("publication_status") or "").strip(),
            confidence_reason_codes=tuple(
                str(item).strip() for item in raw_expected_policy.get("confidence_reason_codes") or ()
            ),
        ),
    )


def _parse_document(raw_document: Any) -> St025FixtureDocument:
    document = cast(dict[str, Any], raw_document)
    raw_spans = document.get("spans") or []
    if not isinstance(raw_spans, list):
        raise ValueError("ST-025 fixture document spans must be a list.")

    return St025FixtureDocument(
        document_id=str(document.get("document_id") or "").strip(),
        document_kind=cast(DocumentKind, str(document.get("document_kind") or "").strip()),
        revision_id=str(document.get("revision_id") or "").strip(),
        revision_number=int(document.get("revision_number") or 0),
        is_active_revision=bool(document.get("is_active_revision")),
        extracted_at=str(document.get("extracted_at") or "").strip(),
        authority_level=str(document.get("authority_level") or "").strip(),
        authority_source=str(document.get("authority_source") or "").strip(),
        authority_note=(str(document.get("authority_note")).strip() if document.get("authority_note") is not None else None),
        spans=tuple(_parse_span(raw_span) for raw_span in raw_spans),
    )


def _parse_span(raw_span: Any) -> St025FixtureSpan:
    span = cast(dict[str, Any], raw_span)
    raw_signal_tags = span.get("signal_tags") or []
    if not isinstance(raw_signal_tags, list):
        raise ValueError("ST-025 fixture span signal_tags must be a list.")
    return St025FixtureSpan(
        stable_section_path=str(span.get("stable_section_path") or "").strip(),
        text=str(span.get("text") or "").strip(),
        precision=str(span.get("precision") or "").strip(),
        confidence=str(span.get("confidence") or "").strip(),
        signal_tags=tuple(str(item).strip() for item in raw_signal_tags if str(item).strip()),
    )


def _validate_fixture(fixture: St025FixtureScenario) -> None:
    required_fields = (
        fixture.fixture_id,
        fixture.scenario_group,
        fixture.description,
        fixture.meeting_id,
        fixture.meeting_uid,
        fixture.meeting_datetime_utc,
        fixture.expected_policy.authority_outcome,
        fixture.expected_policy.publication_status,
    )
    if any(not field for field in required_fields):
        raise ValueError(f"ST-025 fixture {fixture.fixture_id or '<unknown>'} has blank required fields.")

    if fixture.scenario_group not in {"source_conflict", "partial_coverage", "weak_precision"}:
        raise ValueError(f"ST-025 fixture {fixture.fixture_id} has unsupported scenario_group {fixture.scenario_group!r}.")

    if fixture.expected_compose.source_order != EXPECTED_SOURCE_TYPES:
        raise ValueError(f"ST-025 fixture {fixture.fixture_id} must use source_order={EXPECTED_SOURCE_TYPES}.")

    if tuple(fixture.expected_compose.source_statuses.keys()) != EXPECTED_SOURCE_TYPES:
        raise ValueError(f"ST-025 fixture {fixture.fixture_id} must declare source_statuses for minutes, agenda, packet in order.")

    if set(fixture.expected_compose.source_statuses.values()) - {"present", "partial", "missing"}:
        raise ValueError(f"ST-025 fixture {fixture.fixture_id} contains unsupported source coverage status values.")

    if fixture.expected_policy.publication_status not in {"processed", "limited_confidence"}:
        raise ValueError(f"ST-025 fixture {fixture.fixture_id} has unsupported publication_status.")

    if fixture.scenario_group == "weak_precision" and "weak_precision" not in collect_precision_signal_tags(scenario=fixture):
        raise ValueError(f"ST-025 weak_precision fixture {fixture.fixture_id} must carry a weak_precision signal tag.")

    for document in fixture.documents:
        if not all(
            (
                document.document_id,
                document.document_kind,
                document.revision_id,
                document.extracted_at,
                document.authority_level,
                document.authority_source,
            )
        ):
            raise ValueError(f"ST-025 fixture {fixture.fixture_id} has a document with blank required fields.")
        for span in document.spans:
            if not all((span.stable_section_path, span.text, span.precision, span.confidence)):
                raise ValueError(f"ST-025 fixture {fixture.fixture_id} has a span with blank required fields.")
