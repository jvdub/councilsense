from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from councilsense.app import local_runtime


def _stub_fetch(_: str, __: float) -> bytes:
    url = _
    if "/events?" in url or url.endswith("/events"):
        return (
            '{"value":[{"id":21,"eventName":"City Council Meeting","eventDate":"2026-01-08T00:00:00Z",'
            '"publishedFiles":[{"type":"Minutes","name":"Approved Minutes","fileId":1102,"url":"stream/fixture-minutes.pdf"}]}]}'
        ).encode("utf-8")
    if "GetMeetingFile(" in url and "plainText=true" in url:
        return b'{"blobUri":"https://blob.example/minutes.txt"}'
    if "GetMeetingFile(" in url and "plainText=false" in url:
        return b'{"blobUri":"https://blob.example/minutes.pdf"}'
    if url.endswith("minutes.txt"):
        return b"City Council approved minutes and directed staff to publish updates."
    return b"%PDF-1.7\nmock pdf bytes"


def test_process_latest_marks_run_failed_when_publish_stage_errors(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-terminal-status.db"
    monkeypatch.setenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr("councilsense.app.local_latest_fetch._fetch_url_bytes", _stub_fetch)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_runtime.py",
            "--db-path",
            str(db_path),
            "fetch-latest",
            "--city-id",
            "city-eagle-mountain-ut",
        ],
    )
    local_runtime.main()
    capsys.readouterr()

    def _raise_publish(*args, **kwargs):
        raise RuntimeError("publish exploded")

    monkeypatch.setattr("councilsense.app.local_pipeline.publish_summarization_output", _raise_publish)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_runtime.py",
            "--db-path",
            str(db_path),
            "process-latest",
            "--city-id",
            "city-eagle-mountain-ut",
            "--llm-provider",
            "none",
        ],
    )
    local_runtime.main()

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "failed"
    assert payload["error_summary"]["stage"] == "publish"

    publish_stage = next(item for item in payload["stage_outcomes"] if item["stage"] == "publish")
    assert publish_stage["status"] == "failed"

    connection = sqlite3.connect(db_path)
    status_row = connection.execute(
        "SELECT status FROM processing_runs WHERE id = ?",
        (payload["run_id"],),
    ).fetchone()
    assert status_row is not None
    assert str(status_row[0]) == "failed"
