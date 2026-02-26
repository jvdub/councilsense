from __future__ import annotations

import json
from pathlib import Path

import pytest

from minutes_spike import cli
from minutes_spike import llm


def _write_fake_pdf(path: Path, content: bytes = b"%PDF-1.4\n%fake\n") -> None:
    path.write_bytes(content)


def test_pass_a_includes_llm_provenance_non_toon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules: []\noutput: {evidence: {}}\nllm: {provider: ollama, endpoint: http://localhost:11434, model: fake, timeout_s: 1}\n",
        encoding="utf-8",
    )

    sample = "1. CALL TO ORDER\nMayor opened the meeting.\n\n"
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            return llm.SummaryResult(bullets=["Bullet"], raw_text="Bullet")

    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: _FakeProvider())

    out_path = tmp_path / "out.json"
    rc = cli.main(["--pdf", str(pdf_path), "--profile", str(profile_path), "--summarize-first-item", "--out", str(out_path)])
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    run = payload.get("llm_summary_run")
    assert isinstance(run, dict)
    assert isinstance(run.get("generated_at"), str) and run["generated_at"].endswith("Z")
    assert isinstance(run.get("llm"), dict)
    assert run["llm"].get("provider") == "ollama"
    assert run["llm"].get("model") == "fake"
    assert isinstance(run.get("prompt_template"), dict)
    assert run["prompt_template"].get("id") == "summarize_agenda_item.bullets"
    assert run["prompt_template"].get("version") == 1

    pass_a = payload["agenda_items"][0]["pass_a"]
    prov = pass_a.get("provenance")
    assert isinstance(prov, dict)
    assert isinstance(prov.get("generated_at"), str) and prov["generated_at"].endswith("Z")

    llm_cfg = prov.get("llm")
    assert isinstance(llm_cfg, dict)
    assert llm_cfg.get("provider") == "ollama"
    assert llm_cfg.get("model") == "fake"

    prompt = prov.get("prompt_template")
    assert isinstance(prompt, dict)
    assert prompt.get("id") == "summarize_agenda_item.bullets"
    assert prompt.get("version") == 1


def test_toon_roundtrip_includes_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules: []\noutput: {evidence: {}}\nllm: {provider: ollama, endpoint: http://localhost:11434, model: fake, timeout_s: 1}\n",
        encoding="utf-8",
    )

    sample = (
        "1. CALL TO ORDER\n"
        "Mayor opened the meeting.\n\n"
        "2. ADJOURNMENT\n"
        "Meeting ended.\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def generate_text(self, *, prompt: str) -> str:
            assert "INPUT_TOON" in prompt
            return "summary:\n  - First\ncitations:\n  - \"Mayor opened the meeting\"\n"

        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            raise AssertionError("summarize_agenda_item should not be used in TOON mode")

    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: _FakeProvider())

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--summarize-first-item",
            "--llm-use-toon",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    run = payload.get("llm_summary_run")
    assert isinstance(run, dict)
    assert isinstance(run.get("generated_at"), str) and run["generated_at"].endswith("Z")
    assert isinstance(run.get("llm"), dict)
    assert run["llm"].get("provider") == "ollama"
    assert run["llm"].get("model") == "fake"
    assert isinstance(run.get("prompt_template"), dict)
    assert run["prompt_template"].get("id") == "summarize_agenda_item.toon"
    assert run["prompt_template"].get("version") == 1

    rt = payload["agenda_items"][0]["llm_roundtrip"]
    assert rt.get("mode") == "toon"
    assert isinstance(rt.get("generated_at"), str) and rt["generated_at"].endswith("Z")

    llm_cfg = rt.get("llm")
    assert isinstance(llm_cfg, dict)
    assert llm_cfg.get("provider") == "ollama"
    assert llm_cfg.get("model") == "fake"

    prompt = rt.get("prompt_template")
    assert isinstance(prompt, dict)
    assert prompt.get("id") == "summarize_agenda_item.toon"
    assert prompt.get("version") == 1
