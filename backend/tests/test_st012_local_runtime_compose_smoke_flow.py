from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from councilsense.app import local_runtime
from councilsense.app.local_runtime import (
    get_smoke_state,
    initialize_local_runtime_db,
    run_worker_once,
    seed_processing_fixture,
)
from councilsense.db import MeetingReadRepository


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_local_runtime_artifacts_exist() -> None:
    repo_root = _repo_root()
    assert (repo_root / "docker-compose.local.yml").exists()
    assert (repo_root / "scripts" / "local_runtime_smoke.sh").exists()
    assert (repo_root / "docs" / "runbooks" / "st-012-local-runtime-quickstart.md").exists()


def test_fixture_and_worker_flow_are_idempotent_under_rerun(tmp_path: Path) -> None:
    db_path = tmp_path / "local-runtime-smoke.db"
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")

    initialize_local_runtime_db(connection)

    first_process = seed_processing_fixture(connection)
    first_worker = run_worker_once(connection)
    first_state = get_smoke_state(connection)

    assert first_process["notifications_enqueued"] == 1
    assert first_process["notifications_dedupe_conflicts"] == 0
    assert first_worker["sent_count"] == 1
    assert first_state["outbox_status_counts"] == {"sent": 1}

    second_process = seed_processing_fixture(connection)
    second_worker = run_worker_once(connection)
    second_state = get_smoke_state(connection)

    assert second_process["notifications_enqueued"] == 0
    assert second_process["notifications_dedupe_conflicts"] == 1
    assert second_worker["sent_count"] == 0
    assert second_state["outbox_status_counts"] == {"sent": 1}


def test_seed_processing_fixture_promotes_resident_facing_eagle_mountain_review_copy(tmp_path: Path) -> None:
    db_path = tmp_path / "local-runtime-review-copy.db"
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")

    initialize_local_runtime_db(connection)

    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (
            local_runtime._FIXTURE_MEETING_ID,
            "city-eagle-mountain-ut",
            local_runtime._FIXTURE_MEETING_UID,
            "Local Runtime Smoke Meeting",
        ),
    )
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-03-01T00:00:00Z')
        """,
        (
            "pub-local-runtime-smoke-001",
            local_runtime._FIXTURE_MEETING_ID,
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

    seed_processing_fixture(connection)

    meeting_row = connection.execute(
        "SELECT title FROM meetings WHERE id = ?",
        (local_runtime._FIXTURE_MEETING_ID,),
    ).fetchone()
    latest_publication = connection.execute(
        """
        SELECT
            id,
            version_no,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json
        FROM summary_publications
        WHERE meeting_id = ?
        ORDER BY version_no DESC, published_at DESC, id DESC
        LIMIT 1
        """,
        (local_runtime._FIXTURE_MEETING_ID,),
    ).fetchone()
    evidence_rows = connection.execute(
        """
        SELECT
            pc.claim_text,
            cep.excerpt,
            cep.document_id,
            cep.span_id,
            cep.document_kind,
            cep.section_path,
            cep.precision,
            cep.confidence
        FROM publication_claims pc
        INNER JOIN claim_evidence_pointers cep ON cep.claim_id = pc.id
        WHERE pc.publication_id = ?
        ORDER BY pc.claim_order ASC
        """,
        (local_runtime._FIXTURE_PUBLICATION_ID,),
    ).fetchall()
    canonical_document = connection.execute(
        """
        SELECT document_kind, source_document_url, is_active_revision
        FROM canonical_documents
        WHERE id = ?
        """,
        (local_runtime._FIXTURE_DOCUMENT_ID,),
    ).fetchone()

    detail = MeetingReadRepository(connection).get_meeting_detail(
        meeting_id=local_runtime._FIXTURE_MEETING_ID,
    )

    assert meeting_row == (local_runtime._FIXTURE_TITLE,)
    assert latest_publication is not None
    assert latest_publication[0] == local_runtime._FIXTURE_PUBLICATION_ID
    assert latest_publication[1] == local_runtime._FIXTURE_PUBLICATION_VERSION
    assert latest_publication[2] == local_runtime._FIXTURE_SUMMARY
    assert json.loads(latest_publication[3]) == list(local_runtime._FIXTURE_DECISIONS)
    assert json.loads(latest_publication[4]) == list(local_runtime._FIXTURE_ACTIONS)
    assert json.loads(latest_publication[5]) == list(local_runtime._FIXTURE_TOPICS)
    assert canonical_document == ("minutes", local_runtime._FIXTURE_SOURCE_DOCUMENT_URL, 1)
    assert detail is not None
    assert detail.meeting_date == "2024-12-03"
    assert detail.body_name == "Eagle Mountain City Council"
    assert detail.source_document_kind == "minutes"
    assert detail.source_document_url == local_runtime._FIXTURE_SOURCE_DOCUMENT_URL
    assert len(detail.claims) == 3
    assert len(evidence_rows) == 3
    assert evidence_rows[0][:2] == (
        local_runtime._FIXTURE_CLAIMS[0]["claim_text"],
        local_runtime._FIXTURE_CLAIMS[0]["excerpt"],
    )
    assert evidence_rows[1][:2] == (
        local_runtime._FIXTURE_CLAIMS[1]["claim_text"],
        local_runtime._FIXTURE_CLAIMS[1]["excerpt"],
    )
    assert evidence_rows[2][:2] == (
        local_runtime._FIXTURE_CLAIMS[2]["claim_text"],
        local_runtime._FIXTURE_CLAIMS[2]["excerpt"],
    )
    assert all(row[2] == local_runtime._FIXTURE_DOCUMENT_ID for row in evidence_rows)
    assert all(row[4] == "minutes" for row in evidence_rows)
    assert all(row[5] is not None for row in evidence_rows)
    assert all(row[6] == "span" for row in evidence_rows)
    assert all(row[7] == "high" for row in evidence_rows)
