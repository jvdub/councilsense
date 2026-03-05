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
    MeetingWriteRepository,
    PILOT_CITY_ID,
    apply_migrations,
    seed_city_registry,
)


_DEFAULT_DB_PATH = "/data/councilsense-local.db"
_FIXTURE_MEETING_ID = "meeting-local-runtime-smoke-001"
_FIXTURE_MEETING_UID = "local-runtime-smoke-uid-001"
_FIXTURE_PUBLICATION_ID = "pub-local-runtime-smoke-001"
_FIXTURE_CLAIM_ID = "claim-local-runtime-smoke-001"
_FIXTURE_POINTER_ID = "pointer-local-runtime-smoke-001"


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

    meeting = write_repository.upsert_meeting(
        meeting_id=_FIXTURE_MEETING_ID,
        meeting_uid=_FIXTURE_MEETING_UID,
        city_id=PILOT_CITY_ID,
        title="Local Runtime Smoke Meeting",
    )

    existing_publication = connection.execute(
        "SELECT 1 FROM summary_publications WHERE id = ?",
        (_FIXTURE_PUBLICATION_ID,),
    ).fetchone()

    with connection:
        if existing_publication is None:
            connection.execute(
                """
                INSERT INTO summary_publications (
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
                    _FIXTURE_PUBLICATION_ID,
                    meeting.id,
                    None,
                    None,
                    1,
                    "processed",
                    "high",
                    "Deterministic local runtime summary for smoke validation.",
                    json.dumps(["Approved deterministic smoke fixture"], separators=(",", ":")),
                    json.dumps(["Publish local runtime artifact"], separators=(",", ":")),
                    json.dumps(["runtime", "smoke"], separators=(",", ":")),
                ),
            )
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
                _FIXTURE_CLAIM_ID,
                _FIXTURE_PUBLICATION_ID,
                1,
                "Local runtime smoke fixture claim.",
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
                excerpt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _FIXTURE_POINTER_ID,
                _FIXTURE_CLAIM_ID,
                "artifact-local-runtime-smoke-001",
                "minutes.section.1",
                0,
                42,
                "Evidence excerpt for local runtime smoke fixture.",
            ),
        )

    enqueue_result = enqueue_publish_notifications_to_outbox(
        connection=connection,
        city_id=PILOT_CITY_ID,
        meeting_id=meeting.id,
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
        "meeting_inserted": 1,
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