from __future__ import annotations

import json
import sys
from pathlib import Path

from councilsense.app import local_runtime


def _stub_fetch(_: str, __: float) -> bytes:
    return (
        "<html><body>"
        "<a href='/agenda/2026-02-11-minutes.pdf'>City Council Minutes - 02/11/2026</a>"
        "</body></html>"
    ).encode("utf-8")


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

    def _raise_ollama(*, text: str, artifact_id: str, section_ref: str, endpoint: str, model: str, timeout_seconds: float):
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
