from __future__ import annotations

import json
import sys
from pathlib import Path

from councilsense.app import local_runtime
from councilsense.app.local_latest_fetch import LatestFetchError


def _stub_fetch(url: str, __: float) -> bytes:
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


def test_process_latest_contract_and_stage_ordering(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-process-latest.db"
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
    assert payload["command"] == "process-latest"
    assert payload["status"] == "processed"
    assert payload["error_summary"] is None
    assert [item["stage"] for item in payload["stage_outcomes"]] == ["extract", "summarize", "publish"]


def test_run_latest_contract_includes_ingest_then_process_stages(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-run-latest.db"
    monkeypatch.setenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr("councilsense.app.local_latest_fetch._fetch_url_bytes", _stub_fetch)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_runtime.py",
            "--db-path",
            str(db_path),
            "run-latest",
            "--city-id",
            "city-eagle-mountain-ut",
            "--llm-provider",
            "none",
        ],
    )
    local_runtime.main()

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["command"] == "run-latest"
    assert payload["status"] == "processed"
    assert payload["error_summary"] is None
    assert [item["stage"] for item in payload["stage_outcomes"]] == ["ingest", "extract", "summarize", "publish"]


def test_run_latest_falls_back_to_fixture_when_fetch_fails(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-run-latest-fallback.db"

    def _raise_fetch(_: str, __: float) -> bytes:
        raise LatestFetchError("source temporarily unavailable")

    monkeypatch.setattr("councilsense.app.local_latest_fetch._fetch_url_bytes", _raise_fetch)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_runtime.py",
            "--db-path",
            str(db_path),
            "run-latest",
            "--city-id",
            "city-eagle-mountain-ut",
            "--llm-provider",
            "none",
        ],
    )
    local_runtime.main()

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["command"] == "run-latest"
    assert payload["status"] in {"processed", "limited_confidence"}
    assert payload["error_summary"] is None
    assert "fetch_latest_failed_fallback_to_fixture" in payload["warnings"]
    assert payload["meeting_id"] == "meeting-local-runtime-smoke-001"
    assert [item["stage"] for item in payload["stage_outcomes"]] == ["ingest", "extract", "summarize", "publish"]
    assert payload["stage_outcomes"][0]["metadata"]["fallback"] == "fixture"
