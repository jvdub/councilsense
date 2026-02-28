from __future__ import annotations

import sqlite3
from pathlib import Path

from councilsense.app.local_runtime import (
    get_smoke_state,
    initialize_local_runtime_db,
    run_worker_once,
    seed_processing_fixture,
)


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
