from __future__ import annotations

import json
import sys
from pathlib import Path

from councilsense.app import local_runtime


def test_fetch_latest_command_emits_expected_json_envelope(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-fetch-latest.db"

    def _stub_fetch(url: str, timeout_seconds: float) -> bytes:
        assert timeout_seconds == 3.0
        if "/events?" in url or url.endswith("/events"):
            return (
                '{"value":[{"id":2,"eventName":"City Council Meeting","eventDate":"2026-02-11T00:00:00Z",'
                '"publishedFiles":[{"type":"Minutes","name":"Approved Minutes","fileId":1305,"url":"stream/new-minutes.pdf"}]}]}'
            ).encode("utf-8")
        if "GetMeetingFile(" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/minutes.txt"}'
        if "GetMeetingFile(" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/minutes.pdf"}'
        if url.endswith("minutes.txt"):
            return b"City Council approved minutes for February 11, 2026."
        assert "blob.example" in url or "civicclerk.com" in url
        return b"%PDF-1.7\nmock pdf bytes"

    monkeypatch.setattr("councilsense.app.local_latest_fetch._fetch_url_bytes", _stub_fetch)
    monkeypatch.setenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
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
            "--timeout-seconds",
            "3.0",
        ],
    )

    local_runtime.main()

    stdout = capsys.readouterr().out.strip()
    payload = json.loads(stdout)

    assert payload["command"] == "fetch-latest"
    assert payload["city_id"] == "city-eagle-mountain-ut"
    assert payload["status"] == "processed"
    assert isinstance(payload["run_id"], str) and payload["run_id"]
    assert isinstance(payload["source_id"], str) and payload["source_id"]
    assert isinstance(payload["meeting_id"], str) and payload["meeting_id"]
    assert payload["error_summary"] is None
    assert payload["warnings"] == []

    stage_outcomes = payload["stage_outcomes"]
    assert isinstance(stage_outcomes, list)
    assert len(stage_outcomes) == 1
    assert stage_outcomes[0]["stage"] == "ingest"
    assert stage_outcomes[0]["status"] == "processed"
