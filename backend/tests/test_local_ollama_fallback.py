from __future__ import annotations

import json
import sys
from pathlib import Path

from councilsense.app import local_runtime


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


def test_process_latest_ollama_unavailable_falls_back_to_deterministic(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-ollama-fallback.db"
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

    def _raise_ollama(
        *,
        text: str,
        artifact_id: str,
        section_ref: str,
        compose_input,
        material_context,
        authority_policy,
        topic_hardening_enabled: bool,
        specificity_retention_enabled: bool,
        evidence_projection_enabled: bool,
        endpoint: str,
        model: str,
        timeout_seconds: float,
    ):
        raise RuntimeError("endpoint unavailable")

    monkeypatch.setattr("councilsense.app.local_pipeline._summarize_with_ollama", _raise_ollama)

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
            "ollama",
            "--ollama-endpoint",
            "http://127.0.0.1:9",
        ],
    )
    local_runtime.main()

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "limited_confidence"
    assert "ollama_fallback_to_deterministic" in payload["warnings"]

    summarize_stage = next(item for item in payload["stage_outcomes"] if item["stage"] == "summarize")
    assert summarize_stage["status"] == "limited_confidence"
    assert summarize_stage["metadata"]["provider_used"] == "deterministic_fallback"
    assert "endpoint unavailable" in summarize_stage["metadata"]["fallback_reason"]
