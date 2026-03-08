from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from councilsense.app.canonical_persistence import run_pilot_canonical_backfill
from councilsense.app.local_latest_fetch import LatestFetchError, fetch_latest_meeting
from councilsense.app.local_pipeline import LocalPipelineOrchestrator
from councilsense.app.notification_delivery_worker import NotificationDeliveryWorker
from councilsense.app.notification_fanout import (
    NotificationSubscriptionTarget,
    enqueue_publish_notifications_to_outbox,
)
from councilsense.db import (
    CanonicalDocumentRepository,
    MeetingWriteRepository,
    PILOT_CITY_ID,
    apply_migrations,
    seed_city_registry,
)


_DEFAULT_DB_PATH = "/data/councilsense-local.db"
_FIXTURE_MEETING_ID = "meeting-local-runtime-smoke-001"
_FIXTURE_MEETING_UID = "local-runtime-smoke-uid-001"
_FIXTURE_TITLE = "Eagle Mountain City Council Regular Meeting"
_FIXTURE_PUBLICATION_ID = "pub-local-runtime-eaglemountain-review-v4"
_FIXTURE_PUBLICATION_VERSION = 4
_FIXTURE_ARTIFACT_ID = "artifact-local-runtime-eaglemountain-review-v4"
_FIXTURE_DOCUMENT_ID = "canonical-local-runtime-eaglemountain-review-v4"
_FIXTURE_DOCUMENT_REVISION_ID = "local-runtime-eaglemountain-review-v4"
_FIXTURE_DOCUMENT_REVISION_NUMBER = 2
_FIXTURE_SOURCE_DOCUMENT_URL = "https://eaglemountainut.portal.civicclerk.com/event/146/media"
_FIXTURE_MEETING_DATE = "2026-02-18"
_FIXTURE_SUMMARY = (
    "The council reviewed major residential development proposals totaling 893 units across 208 acres, "
    "approved the Old Airport Road right-of-way acquisition and a school-district boundary property title "
    "transfer, and adopted the 2025 meeting schedule with added November 5 and December 16 dates."
)
_FIXTURE_DECISIONS = (
    "Approved a Purchase Agreement with Ivory Land Corporation for acquisition of right-of-way for Old Airport Road, North.",
    "Consented to transfer of title for property located in the interlocal boundary of the new school district in West Utah County.",
    "Approved the 2025 City Council meeting schedule, including added dates on November 5 and December 16.",
)
_FIXTURE_ACTIONS = (
    "Removed one item from the consent agenda and moved it to a scheduled item for further discussion.",
    "Adopted schedule changes adding meetings on November 5 and December 16.",
)
_FIXTURE_TOPICS = (
    "Residential growth and land use scale",
    "Right-of-way acquisition and property transfer",
    "2025 meeting schedule updates",
)
_FIXTURE_CLAIMS = (
    {
        "claim_id": "claim-local-runtime-eaglemountain-review-v4-1",
        "pointer_id": "pointer-local-runtime-eaglemountain-review-v4-1",
        "span_id": "span-local-runtime-eaglemountain-review-v4-1",
        "claim_text": "The council reviewed residential development proposals totaling 893 units across 208 acres, including open space and HOA park considerations.",
        "section_ref": "minutes.section.7",
        "section_path": "minutes/section/7",
        "char_start": 0,
        "excerpt": (
            "The council reviewed proposed residential developments totaling 893 units across 208 acres, including open space requirements and HOA parks."
        ),
    },
    {
        "claim_id": "claim-local-runtime-eaglemountain-review-v4-2",
        "pointer_id": "pointer-local-runtime-eaglemountain-review-v4-2",
        "span_id": "span-local-runtime-eaglemountain-review-v4-2",
        "claim_text": "The council approved a Purchase Agreement with Ivory Land Corporation for the Old Airport Road, North right-of-way acquisition.",
        "section_ref": "minutes.section.8",
        "section_path": "minutes/section/8",
        "char_start": 144,
        "excerpt": (
            "Approved a Purchase Agreement with Ivory Land Corporation for the Acquisition of Right-of-Way for Old Airport Road, North."
        ),
    },
    {
        "claim_id": "claim-local-runtime-eaglemountain-review-v4-3",
        "pointer_id": "pointer-local-runtime-eaglemountain-review-v4-3",
        "span_id": "span-local-runtime-eaglemountain-review-v4-3",
        "claim_text": "The council approved the 2025 meeting schedule, including added dates on November 5 and December 16.",
        "section_ref": "minutes.section.11",
        "section_path": "minutes/section/11",
        "char_start": 288,
        "excerpt": (
            "Approved the 2025 City Council Meeting Schedule, adding meetings on November 5 and December 16."
        ),
    },
)


def _fixture_history() -> tuple[dict[str, Any], ...]:
    return (
        {
            "meeting_id": _FIXTURE_MEETING_ID,
            "meeting_uid": _FIXTURE_MEETING_UID,
            "title": _FIXTURE_TITLE,
            "created_at": "2026-02-18 18:30:00",
            "updated_at": "2026-02-18 19:12:00",
            "meeting_date": _FIXTURE_MEETING_DATE,
            "body_name": "Eagle Mountain City Council",
            "publication_id": _FIXTURE_PUBLICATION_ID,
            "publication_version": _FIXTURE_PUBLICATION_VERSION,
            "artifact_id": _FIXTURE_ARTIFACT_ID,
            "document_id": _FIXTURE_DOCUMENT_ID,
            "document_revision_id": _FIXTURE_DOCUMENT_REVISION_ID,
            "document_revision_number": _FIXTURE_DOCUMENT_REVISION_NUMBER,
            "source_document_url": _FIXTURE_SOURCE_DOCUMENT_URL,
            "authority_note": "Grounded local review fixture for Eagle Mountain detail verification.",
            "selected_event_name": "Eagle Mountain City Council",
            "summary": _FIXTURE_SUMMARY,
            "decisions": _FIXTURE_DECISIONS,
            "actions": _FIXTURE_ACTIONS,
            "topics": _FIXTURE_TOPICS,
            "claims": _FIXTURE_CLAIMS,
            "processing_run_id": "run-local-runtime-eaglemountain-review-v3",
            "cycle_id": "cycle-local-runtime-eaglemountain-review-v3",
            "stage_outcome_id": "outcome-ingest-local-runtime-eaglemountain-review-v3",
        },
        {
            "meeting_id": "meeting-local-runtime-smoke-002",
            "meeting_uid": "local-runtime-smoke-uid-002",
            "title": "Eagle Mountain City Council Work Session",
            "created_at": "2026-01-21 18:00:00",
            "updated_at": "2026-01-21 18:47:00",
            "meeting_date": "2026-01-21",
            "body_name": "Eagle Mountain City Council",
            "publication_id": "pub-local-runtime-eaglemountain-review-history-002",
            "publication_version": 1,
            "artifact_id": "artifact-local-runtime-eaglemountain-review-history-002",
            "document_id": "canonical-local-runtime-eaglemountain-review-history-002",
            "document_revision_id": "local-runtime-eaglemountain-review-history-002",
            "document_revision_number": 1,
            "source_document_url": "https://eaglemountainut.portal.civicclerk.com/event/153/media",
            "authority_note": "Local review fixture showing recurring January Eagle Mountain processing.",
            "selected_event_name": "Eagle Mountain City Council",
            "summary": (
                "The council advanced the Cory Wride memorial park phase plan, directed staff to return with a "
                "costed trail-lighting option, and approved a snow-event overtime budget amendment before the "
                "next storm cycle."
            ),
            "decisions": (
                "Approved the snow-event overtime budget amendment for the public works response window.",
                "Advanced the memorial park phase plan for final contract drafting.",
            ),
            "actions": (
                "Directed staff to return with a trail-lighting cost comparison and grant options.",
                "Requested the parks team to publish a revised phase map before the February regular meeting.",
            ),
            "topics": (
                "Memorial park phase planning",
                "Snow response resourcing",
                "Trail-lighting scope",
            ),
            "claims": (
                {
                    "claim_id": "claim-local-runtime-eaglemountain-review-history-002-1",
                    "pointer_id": "pointer-local-runtime-eaglemountain-review-history-002-1",
                    "span_id": "span-local-runtime-eaglemountain-review-history-002-1",
                    "claim_text": "The council approved a snow-event overtime budget amendment for public works before the next storm cycle.",
                    "section_ref": "minutes.section.5",
                    "section_path": "minutes/section/5",
                    "char_start": 0,
                    "excerpt": "The council approved a snow-event overtime budget amendment so public works crews could cover the next storm cycle.",
                },
                {
                    "claim_id": "claim-local-runtime-eaglemountain-review-history-002-2",
                    "pointer_id": "pointer-local-runtime-eaglemountain-review-history-002-2",
                    "span_id": "span-local-runtime-eaglemountain-review-history-002-2",
                    "claim_text": "Staff was directed to return with trail-lighting cost comparisons and grant options.",
                    "section_ref": "minutes.section.7",
                    "section_path": "minutes/section/7",
                    "char_start": 164,
                    "excerpt": "Council directed staff to return with trail-lighting cost comparisons, grant options, and a maintenance estimate.",
                },
            ),
            "processing_run_id": "run-local-runtime-eaglemountain-review-history-002",
            "cycle_id": "cycle-local-runtime-eaglemountain-review-history-002",
            "stage_outcome_id": "outcome-ingest-local-runtime-eaglemountain-review-history-002",
        },
        {
            "meeting_id": "meeting-local-runtime-smoke-003",
            "meeting_uid": "local-runtime-smoke-uid-003",
            "title": "Eagle Mountain City Council Regular Meeting",
            "created_at": "2025-12-16 18:30:00",
            "updated_at": "2025-12-16 19:05:00",
            "meeting_date": "2025-12-16",
            "body_name": "Eagle Mountain City Council",
            "publication_id": "pub-local-runtime-eaglemountain-review-history-003",
            "publication_version": 1,
            "artifact_id": "artifact-local-runtime-eaglemountain-review-history-003",
            "document_id": "canonical-local-runtime-eaglemountain-review-history-003",
            "document_revision_id": "local-runtime-eaglemountain-review-history-003",
            "document_revision_number": 1,
            "source_document_url": "https://eaglemountainut.portal.civicclerk.com/event/149/media",
            "authority_note": "Local review fixture showing recurring December Eagle Mountain processing.",
            "selected_event_name": "Eagle Mountain City Council",
            "summary": (
                "The council adopted a utility-rate transition schedule, approved a downtown wayfinding sign package, "
                "and asked staff to publish a resident FAQ covering billing changes before January statements go out."
            ),
            "decisions": (
                "Adopted the utility-rate transition schedule effective with January billing.",
                "Approved the downtown wayfinding sign package and fabrication bid.",
            ),
            "actions": (
                "Directed staff to publish a resident FAQ before January utility statements are mailed.",
                "Asked engineering to verify installation sequencing for the sign package.",
            ),
            "topics": (
                "Utility-rate transition",
                "Downtown wayfinding signage",
                "Resident billing communications",
            ),
            "claims": (
                {
                    "claim_id": "claim-local-runtime-eaglemountain-review-history-003-1",
                    "pointer_id": "pointer-local-runtime-eaglemountain-review-history-003-1",
                    "span_id": "span-local-runtime-eaglemountain-review-history-003-1",
                    "claim_text": "The council adopted a utility-rate transition schedule effective with January billing.",
                    "section_ref": "minutes.section.4",
                    "section_path": "minutes/section/4",
                    "char_start": 0,
                    "excerpt": "The council adopted the utility-rate transition schedule with the first change effective on January billing statements.",
                },
                {
                    "claim_id": "claim-local-runtime-eaglemountain-review-history-003-2",
                    "pointer_id": "pointer-local-runtime-eaglemountain-review-history-003-2",
                    "span_id": "span-local-runtime-eaglemountain-review-history-003-2",
                    "claim_text": "Staff was directed to publish a resident FAQ before January statements are mailed.",
                    "section_ref": "minutes.section.6",
                    "section_path": "minutes/section/6",
                    "char_start": 158,
                    "excerpt": "Staff was directed to publish a resident FAQ on billing changes before January statements are mailed.",
                },
            ),
            "processing_run_id": "run-local-runtime-eaglemountain-review-history-003",
            "cycle_id": "cycle-local-runtime-eaglemountain-review-history-003",
            "stage_outcome_id": "outcome-ingest-local-runtime-eaglemountain-review-history-003",
        },
    )


def _seed_fixture_canonical_minutes(connection: sqlite3.Connection, *, meeting_id: str, fixture: dict[str, Any]) -> None:
    repository = CanonicalDocumentRepository(connection)
    repository.upsert_document_revision(
        canonical_document_id=str(fixture["document_id"]),
        meeting_id=meeting_id,
        document_kind="minutes",
        revision_id=str(fixture["document_revision_id"]),
        revision_number=int(fixture["document_revision_number"]),
        is_active_revision=True,
        authority_level="authoritative",
        authority_source="local-runtime-fixture",
        authority_note=str(fixture["authority_note"]),
        source_document_url=str(fixture["source_document_url"]),
        source_checksum=None,
        parser_name="local-runtime-fixture",
        parser_version="v3",
        extraction_status="processed",
        extraction_confidence=0.99,
        extracted_at="2026-03-07T00:00:00Z",
    )

    for claim in tuple(fixture["claims"]):
        excerpt = str(claim["excerpt"])
        start_offset = int(claim["char_start"])
        repository.upsert_document_span(
            canonical_document_span_id=str(claim["span_id"]),
            canonical_document_id=str(fixture["document_id"]),
            artifact_id=str(fixture["artifact_id"]),
            stable_section_path=str(claim["section_path"]),
            page_number=4,
            line_index=None,
            start_char_offset=start_offset,
            end_char_offset=start_offset + len(excerpt),
            parser_name="local-runtime-fixture",
            parser_version="v3",
            source_chunk_id=None,
            span_text=excerpt,
            span_text_checksum=None,
        )


def _seed_fixture_ingest_context(connection: sqlite3.Connection, *, meeting_id: str, fixture: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO processing_runs (
            id,
            city_id,
            cycle_id,
            status,
            parser_version,
            source_version,
            started_at
        )
        VALUES (?, ?, ?, 'processed', ?, ?, ?)
        """,
        (
            str(fixture["processing_run_id"]),
            PILOT_CITY_ID,
            str(fixture["cycle_id"]),
            "local-runtime-fixture-v3",
            "local-runtime-fixture-v3",
            "2026-03-07T00:00:00Z",
        ),
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO processing_stage_outcomes (
            id,
            run_id,
            city_id,
            meeting_id,
            stage_name,
            status,
            metadata_json,
            started_at,
            finished_at
        )
        VALUES (?, ?, ?, ?, 'ingest', 'processed', ?, ?, ?)
        """,
        (
            str(fixture["stage_outcome_id"]),
            str(fixture["processing_run_id"]),
            PILOT_CITY_ID,
            meeting_id,
            json.dumps(
                {
                    "selected_event_name": str(fixture["selected_event_name"]),
                    "selected_event_date": str(fixture["meeting_date"]),
                    "candidate_url": str(fixture["source_document_url"]),
                },
                separators=(",", ":"),
            ),
            "2026-03-07T00:00:00Z",
            "2026-03-07T00:01:00Z",
        ),
    )


def _seed_fixture_publication(connection: sqlite3.Connection, *, meeting_id: str, fixture: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO summary_publications (
            id,
            meeting_id,
            processing_run_id,
            publish_stage_outcome_id,
            version_no,
            publication_status,
            confidence_label,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json,
            published_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            str(fixture["publication_id"]),
            meeting_id,
            None,
            None,
            int(fixture["publication_version"]),
            "processed",
            "high",
            str(fixture["summary"]),
            json.dumps(tuple(fixture["decisions"]), separators=(",", ":")),
            json.dumps(tuple(fixture["actions"]), separators=(",", ":")),
            json.dumps(tuple(fixture["topics"]), separators=(",", ":")),
        ),
    )

    for claim_order, claim in enumerate(tuple(fixture["claims"]), start=1):
        excerpt = str(claim["excerpt"])
        start_offset = int(claim["char_start"])
        connection.execute(
            """
            INSERT OR IGNORE INTO publication_claims (
                id,
                publication_id,
                claim_order,
                claim_text
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                str(claim["claim_id"]),
                str(fixture["publication_id"]),
                claim_order,
                str(claim["claim_text"]),
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO claim_evidence_pointers (
                id,
                claim_id,
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(claim["pointer_id"]),
                str(claim["claim_id"]),
                str(fixture["artifact_id"]),
                str(claim["section_ref"]),
                start_offset,
                start_offset + len(excerpt),
                excerpt,
                str(fixture["document_id"]),
                str(claim["span_id"]),
                "minutes",
                str(claim["section_path"]),
                "span",
                "high",
            ),
        )


def _seed_fixture_meeting_record(
    connection: sqlite3.Connection,
    *,
    write_repository: MeetingWriteRepository,
    fixture: dict[str, Any],
) -> str:
    meeting = write_repository.upsert_meeting(
        meeting_id=str(fixture["meeting_id"]),
        meeting_uid=str(fixture["meeting_uid"]),
        city_id=PILOT_CITY_ID,
        title=str(fixture["title"]),
    )
    connection.execute(
        """
        UPDATE meetings
        SET title = ?, created_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            str(fixture["title"]),
            str(fixture["created_at"]),
            str(fixture["updated_at"]),
            meeting.id,
        ),
    )
    return meeting.id


def _build_command_envelope(
    *,
    command: str,
    run_id: str,
    city_id: str,
    source_id: str | None,
    meeting_id: str | None,
    status: str,
    stage_outcomes: list[dict[str, object]],
    warnings: list[str],
    error_summary: dict[str, object] | None,
) -> dict[str, Any]:
    return {
        "command": command,
        "run_id": run_id,
        "city_id": city_id,
        "source_id": source_id,
        "meeting_id": meeting_id,
        "status": status,
        "stage_outcomes": stage_outcomes,
        "warnings": warnings,
        "error_summary": error_summary,
    }


def _db_path_from_env() -> str:
    return os.getenv("COUNCILSENSE_SQLITE_PATH", _DEFAULT_DB_PATH)


def _connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_local_runtime_db(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)


def seed_processing_fixture(connection: sqlite3.Connection) -> dict[str, int]:
    initialize_local_runtime_db(connection)

    write_repository = MeetingWriteRepository(connection)

    fixture_history = _fixture_history()
    seeded_meeting_ids: list[str] = []

    with connection:
        for fixture in fixture_history:
            meeting_id = _seed_fixture_meeting_record(
                connection,
                write_repository=write_repository,
                fixture=fixture,
            )
            seeded_meeting_ids.append(meeting_id)
            _seed_fixture_ingest_context(connection, meeting_id=meeting_id, fixture=fixture)
            _seed_fixture_canonical_minutes(connection, meeting_id=meeting_id, fixture=fixture)
            _seed_fixture_publication(connection, meeting_id=meeting_id, fixture=fixture)

    enqueue_result = enqueue_publish_notifications_to_outbox(
        connection=connection,
        city_id=PILOT_CITY_ID,
        meeting_id=_FIXTURE_MEETING_ID,
        subscription_targets=(
            NotificationSubscriptionTarget(
                user_id="user-local-runtime-smoke",
                city_id=PILOT_CITY_ID,
                subscription_id="sub-local-runtime-smoke",
                status="active",
            ),
        ),
    )

    return {
        "meeting_inserted": len(seeded_meeting_ids),
        "notifications_enqueued": enqueue_result.enqueued_count,
        "notifications_dedupe_conflicts": enqueue_result.dedupe_conflict_count,
    }


def run_worker_once(connection: sqlite3.Connection) -> dict[str, int]:
    worker = NotificationDeliveryWorker(connection=connection, sender=lambda _: None)
    result = worker.run_once()
    return {
        "claimed_count": result.claimed_count,
        "sent_count": result.sent_count,
        "retried_count": result.retried_count,
        "failed_count": result.failed_count,
        "suppressed_count": result.suppressed_count,
    }


def get_smoke_state(connection: sqlite3.Connection) -> dict[str, object]:
    publication = connection.execute(
        """
        SELECT id, meeting_id, publication_status
        FROM summary_publications
        WHERE id = ?
        """,
        (_FIXTURE_PUBLICATION_ID,),
    ).fetchone()

    outbox_counts_raw = connection.execute(
        """
        SELECT status, COUNT(*)
        FROM notification_outbox
        WHERE meeting_id = ?
        GROUP BY status
        ORDER BY status
        """,
        (_FIXTURE_MEETING_ID,),
    ).fetchall()
    outbox_counts = {str(row[0]): int(row[1]) for row in outbox_counts_raw}

    return {
        "fixture": {
            "meeting_id": _FIXTURE_MEETING_ID,
            "publication_id": _FIXTURE_PUBLICATION_ID,
            "city_id": PILOT_CITY_ID,
        },
        "publication_present": publication is not None,
        "outbox_status_counts": outbox_counts,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local runtime helper utilities")
    parser.add_argument("--db-path", default=None, help="Override SQLite DB path")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db")
    subparsers.add_parser("process-fixture")
    subparsers.add_parser("worker-once")

    worker_loop = subparsers.add_parser("worker-loop")
    worker_loop.add_argument("--interval-seconds", type=float, default=2.0)

    subparsers.add_parser("smoke-state")

    fetch_latest = subparsers.add_parser("fetch-latest")
    fetch_latest.add_argument("--city-id", default=PILOT_CITY_ID)
    fetch_latest.add_argument("--source-id", default=None)
    fetch_latest.add_argument("--timeout-seconds", type=float, default=12.0)

    process_latest = subparsers.add_parser("process-latest")
    process_latest.add_argument("--city-id", default=PILOT_CITY_ID)
    process_latest.add_argument("--meeting-id", default=None)
    process_latest.add_argument("--llm-provider", choices=("none", "ollama"), default="none")
    process_latest.add_argument("--ollama-endpoint", default=None)
    process_latest.add_argument("--ollama-model", default=None)
    process_latest.add_argument("--ollama-timeout-seconds", type=float, default=20.0)

    run_latest = subparsers.add_parser("run-latest")
    run_latest.add_argument("--city-id", default=PILOT_CITY_ID)
    run_latest.add_argument("--source-id", default=None)
    run_latest.add_argument("--meeting-id", default=None)
    run_latest.add_argument("--timeout-seconds", type=float, default=12.0)
    run_latest.add_argument("--llm-provider", choices=("none", "ollama"), default="none")
    run_latest.add_argument("--ollama-endpoint", default=None)
    run_latest.add_argument("--ollama-model", default=None)
    run_latest.add_argument("--ollama-timeout-seconds", type=float, default=20.0)

    canonical_backfill = subparsers.add_parser("canonical-backfill")
    canonical_backfill.add_argument("--city-id", default=PILOT_CITY_ID)
    canonical_backfill.add_argument("--from-date", default=None)
    canonical_backfill.add_argument("--to-date", default=None)
    canonical_backfill.add_argument("--limit", type=int, default=50)
    canonical_backfill.add_argument("--dry-run", action="store_true")

    return parser.parse_args()


def _resolve_db_path(raw_db_path: str | None) -> str:
    resolved = raw_db_path if raw_db_path is not None else _db_path_from_env()
    path = Path(resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def main() -> None:
    args = _parse_args()
    db_path = _resolve_db_path(args.db_path)

    if args.command == "worker-loop":
        while True:
            with _connect(db_path) as connection:
                initialize_local_runtime_db(connection)
                result = run_worker_once(connection)
            print(json.dumps({"command": "worker-once", "result": result}, separators=(",", ":")))
            time.sleep(max(args.interval_seconds, 0.1))

    with _connect(db_path) as connection:
        if args.command == "init-db":
            initialize_local_runtime_db(connection)
            print(json.dumps({"command": "init-db", "db_path": db_path}, separators=(",", ":")))
            return

        if args.command == "process-fixture":
            result = seed_processing_fixture(connection)
            print(json.dumps({"command": "process-fixture", "result": result}, separators=(",", ":")))
            return

        if args.command == "worker-once":
            initialize_local_runtime_db(connection)
            result = run_worker_once(connection)
            print(json.dumps({"command": "worker-once", "result": result}, separators=(",", ":")))
            return

        if args.command == "fetch-latest":
            initialize_local_runtime_db(connection)
            run_id = f"run-local-fetch-latest-{uuid.uuid4().hex[:12]}"
            try:
                fetch_result = fetch_latest_meeting(
                    connection,
                    city_id=args.city_id,
                    source_id=args.source_id,
                    timeout_seconds=args.timeout_seconds,
                )
                envelope = _build_command_envelope(
                    command="fetch-latest",
                    run_id=run_id,
                    city_id=fetch_result.city_id,
                    source_id=fetch_result.source_id,
                    meeting_id=fetch_result.meeting_id,
                    status="processed",
                    stage_outcomes=list(fetch_result.stage_outcomes),
                    warnings=list(fetch_result.warnings),
                    error_summary=None,
                )
                print(json.dumps(envelope, separators=(",", ":")))
                return
            except LatestFetchError as exc:
                envelope = _build_command_envelope(
                    command="fetch-latest",
                    run_id=run_id,
                    city_id=args.city_id,
                    source_id=args.source_id,
                    meeting_id=None,
                    status="failed",
                    stage_outcomes=[{"stage": "ingest", "status": "failed", "metadata": {}}],
                    warnings=[],
                    error_summary={
                        "stage": "ingest",
                        "error_class": exc.__class__.__name__,
                        "message": str(exc),
                        "operator_hint": "Verify city/source registry configuration and source URL reachability.",
                    },
                )
                print(json.dumps(envelope, separators=(",", ":")))
                return
            except Exception as exc:  # pragma: no cover - defensive guard for runtime operators
                envelope = _build_command_envelope(
                    command="fetch-latest",
                    run_id=run_id,
                    city_id=args.city_id,
                    source_id=args.source_id,
                    meeting_id=None,
                    status="failed",
                    stage_outcomes=[{"stage": "ingest", "status": "failed", "metadata": {}}],
                    warnings=[],
                    error_summary={
                        "stage": "ingest",
                        "error_class": exc.__class__.__name__,
                        "message": str(exc),
                        "operator_hint": "Review runtime logs and validate source parser assumptions.",
                    },
                )
                print(json.dumps(envelope, separators=(",", ":")))
                return

        if args.command == "process-latest":
            initialize_local_runtime_db(connection)
            run_id = f"run-local-process-latest-{uuid.uuid4().hex[:12]}"
            orchestrator = LocalPipelineOrchestrator(connection)
            process_result = orchestrator.process_latest(
                run_id=run_id,
                city_id=args.city_id,
                meeting_id=args.meeting_id,
                ingest_stage_metadata=None,
                llm_provider=args.llm_provider,
                ollama_endpoint=args.ollama_endpoint,
                ollama_model=args.ollama_model,
                ollama_timeout_seconds=args.ollama_timeout_seconds,
            )
            envelope = _build_command_envelope(
                command="process-latest",
                run_id=process_result.run_id,
                city_id=process_result.city_id,
                source_id=process_result.source_id,
                meeting_id=process_result.meeting_id,
                status=process_result.status,
                stage_outcomes=list(process_result.stage_outcomes),
                warnings=list(process_result.warnings),
                error_summary=process_result.error_summary,
            )
            print(json.dumps(envelope, separators=(",", ":")))
            return

        if args.command == "run-latest":
            initialize_local_runtime_db(connection)
            run_id = f"run-local-run-latest-{uuid.uuid4().hex[:12]}"
            fallback_warnings: list[str] = []
            fallback_stage_outcomes: list[dict[str, object]] = []
            fallback_meeting_id: str | None = None
            try:
                fetch_result = fetch_latest_meeting(
                    connection,
                    city_id=args.city_id,
                    source_id=args.source_id,
                    timeout_seconds=args.timeout_seconds,
                )
            except Exception as exc:  # pragma: no cover - handled as local fallback for operator reliability
                seed_processing_fixture(connection)
                fallback_meeting_id = _FIXTURE_MEETING_ID
                fetch_error_message = str(exc)
                fallback_warnings.append("fetch_latest_failed_fallback_to_fixture")
                fallback_stage_outcomes.append(
                    {
                        "stage": "ingest",
                        "status": "limited_confidence",
                        "metadata": {
                            "source_id": args.source_id,
                            "fallback": "fixture",
                            "fallback_meeting_id": _FIXTURE_MEETING_ID,
                            "fetch_error_class": exc.__class__.__name__,
                            "fetch_error_message": fetch_error_message,
                        },
                    }
                )
                fetch_result = None

            orchestrator = LocalPipelineOrchestrator(connection)
            process_result = orchestrator.process_latest(
                run_id=run_id,
                city_id=args.city_id,
                meeting_id=(args.meeting_id or (fetch_result.meeting_id if fetch_result is not None else fallback_meeting_id)),
                ingest_stage_metadata=(
                    fetch_result.stage_outcomes[0].get("metadata")
                    if fetch_result is not None and fetch_result.stage_outcomes
                    else (
                        fallback_stage_outcomes[0].get("metadata")
                        if fallback_stage_outcomes
                        else None
                    )
                ),
                llm_provider=args.llm_provider,
                ollama_endpoint=args.ollama_endpoint,
                ollama_model=args.ollama_model,
                ollama_timeout_seconds=args.ollama_timeout_seconds,
            )

            envelope = _build_command_envelope(
                command="run-latest",
                run_id=process_result.run_id,
                city_id=process_result.city_id,
                source_id=(fetch_result.source_id if fetch_result is not None else process_result.source_id),
                meeting_id=process_result.meeting_id,
                status=process_result.status,
                stage_outcomes=[
                    *(list(fetch_result.stage_outcomes) if fetch_result is not None else fallback_stage_outcomes),
                    *list(process_result.stage_outcomes),
                ],
                warnings=[
                    *(list(fetch_result.warnings) if fetch_result is not None else fallback_warnings),
                    *list(process_result.warnings),
                ],
                error_summary=process_result.error_summary,
            )
            print(json.dumps(envelope, separators=(",", ":")))
            return

        if args.command == "canonical-backfill":
            initialize_local_runtime_db(connection)
            result = run_pilot_canonical_backfill(
                connection,
                city_id=args.city_id,
                start_date=args.from_date,
                end_date=args.to_date,
                limit=args.limit,
                dry_run=bool(args.dry_run),
            )
            print(
                json.dumps(
                    {
                        "command": "canonical-backfill",
                        "result": result.to_payload(),
                    },
                    separators=(",", ":"),
                )
            )
            return

        state = get_smoke_state(connection)
        print(json.dumps({"command": "smoke-state", "state": state}, separators=(",", ":")))


if __name__ == "__main__":
    main()