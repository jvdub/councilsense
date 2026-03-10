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


def test_process_latest_openai_compatible_provider_uses_hosted_config(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-openai-provider.db"
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

    captured: dict[str, object] = {}

    from councilsense.app.summarization import SummarizationOutput

    def _summarization_stub(**kwargs):
        captured.update(
            {
                "endpoint": kwargs["endpoint"],
                "model": kwargs["model"],
                "timeout_seconds": kwargs["timeout_seconds"],
                "api_key": kwargs["api_key"],
            }
        )
        return SummarizationOutput.from_sections(
            summary="Council approved a utility update.",
            key_decisions=("Approved a utility update.",),
            key_actions=("Staff will publish the updated utility schedule.",),
            notable_topics=("Utility updates",),
            claims=(),
        )

    monkeypatch.setattr(
        "councilsense.app.local_pipeline._summarize_with_openai_chat_completion",
        _summarization_stub,
    )

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
            "openai",
            "--llm-endpoint",
            "https://api.example.test/v1",
            "--llm-model",
            "gpt-4.1-mini",
            "--llm-api-key",
            "test-api-key",
            "--llm-timeout-seconds",
            "45",
        ],
    )
    local_runtime.main()

    payload = json.loads(capsys.readouterr().out.strip())
    summarize_stage = next(item for item in payload["stage_outcomes"] if item["stage"] == "summarize")
    assert summarize_stage["metadata"]["provider_used"] == "openai"
    assert captured == {
        "endpoint": "https://api.example.test/v1",
        "model": "gpt-4.1-mini",
        "timeout_seconds": 45.0,
        "api_key": "test-api-key",
    }


def test_process_latest_openai_unavailable_falls_back_to_deterministic(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "local-runtime-openai-fallback.db"
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

    def _raise_openai(**kwargs):
        raise RuntimeError("api unavailable")

    monkeypatch.setattr("councilsense.app.local_pipeline._summarize_with_openai_chat_completion", _raise_openai)

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
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
            "openai",
        ],
    )
    local_runtime.main()

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "limited_confidence"
    assert "openai_fallback_to_deterministic" in payload["warnings"]

    summarize_stage = next(item for item in payload["stage_outcomes"] if item["stage"] == "summarize")
    assert summarize_stage["status"] == "limited_confidence"
    assert summarize_stage["metadata"]["provider_used"] == "deterministic_fallback"
    assert "api unavailable" in summarize_stage["metadata"]["fallback_reason"]
