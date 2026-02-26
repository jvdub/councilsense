from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from minutes_spike import cli, llm
from minutes_spike.rerun import rerun_meeting
from minutes_spike.store import import_meeting


def test_i2_rerun_pass_a_uses_llm_cache_on_second_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "2.A. TEST ITEM\nBody text.\n"),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    # Make the rerun deterministic: force a single agenda item.
    meeting_dir = store_dir / "2026-01-09"
    (meeting_dir / "agenda_items.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "2.A",
                    "title": "Test item",
                    "body_text": "Body text.",
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("rules: []\noutput: {evidence: {}}\n", encoding="utf-8")

    class _FakeProvider(llm.LLMProvider):
        def __init__(self) -> None:
            self.calls = 0

        def generate_text(self, *, prompt: str) -> str:  # pragma: no cover
            raise AssertionError("generate_text should not be used in bullets mode")

        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            self.calls += 1
            return llm.SummaryResult(bullets=["Cached bullet"], raw_text="Cached bullet")

    fake = _FakeProvider()
    monkeypatch.setattr("minutes_spike.rerun.create_llm_provider", lambda _cfg: fake)

    rerun_meeting(
        store_dir=store_dir,
        meeting_id="2026-01-09",
        profile_path=str(profile_path),
        summarize_all_items=True,
        classify_relevance=False,
        summarize_meeting=False,
        llm_provider="fake",
        llm_endpoint="http://fake",
        llm_model="fake-model",
        llm_timeout_s=1,
    )
    assert fake.calls == 1

    first = json.loads((meeting_dir / "agenda_pass_a.json").read_text(encoding="utf-8"))
    assert first[0]["pass_a"]["provenance"]["cache"]["hit"] is False

    # Second run with identical inputs should not call the provider.
    rerun_meeting(
        store_dir=store_dir,
        meeting_id="2026-01-09",
        profile_path=str(profile_path),
        summarize_all_items=True,
        classify_relevance=False,
        summarize_meeting=False,
        llm_provider="fake",
        llm_endpoint="http://fake",
        llm_model="fake-model",
        llm_timeout_s=1,
    )
    assert fake.calls == 1

    second = json.loads((meeting_dir / "agenda_pass_a.json").read_text(encoding="utf-8"))
    assert second[0]["pass_a"]["provenance"]["cache"]["hit"] is True

    # Changing model identity should miss the cache and call the provider again.
    rerun_meeting(
        store_dir=store_dir,
        meeting_id="2026-01-09",
        profile_path=str(profile_path),
        summarize_all_items=True,
        classify_relevance=False,
        summarize_meeting=False,
        llm_provider="fake",
        llm_endpoint="http://fake",
        llm_model="other-model",
        llm_timeout_s=1,
    )
    assert fake.calls == 2


def test_i2_cli_pass_a_uses_llm_cache_when_store_dir_provided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        textwrap.dedent(
            """\
            rules: []
            output: {evidence: {}}
            llm: {provider: ollama, endpoint: http://localhost:11434, model: fake, timeout_s: 1}
            """
        ),
        encoding="utf-8",
    )

    sample = (
        "1. CALL TO ORDER\n"
        "Mayor opened the meeting.\n\n"
        "2.A. DISCUSSION - PARKING UPDATES\n"
        "Staff presented changes and recommended approval.\n\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", sample),
    )

    class _FakeProvider(llm.LLMProvider):
        def __init__(self) -> None:
            self.calls = 0

        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            self.calls += 1
            return llm.SummaryResult(bullets=[f"Summary for {title}"], raw_text=f"Summary for {title}")

    fake = _FakeProvider()
    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: fake)

    store_dir = tmp_path / "store"
    out_path = tmp_path / "out.json"

    rc1 = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--store-dir",
            str(store_dir),
            "--meeting-id",
            "2026-01-09",
            "--summarize-all-items",
            "--out",
            str(out_path),
        ]
    )
    assert rc1 == 0
    assert fake.calls == 2

    rc2 = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--store-dir",
            str(store_dir),
            "--meeting-id",
            "2026-01-09",
            "--summarize-all-items",
            "--out",
            str(out_path),
        ]
    )
    assert rc2 == 0
    assert fake.calls == 2

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["agenda_items"][0]["pass_a"]["provenance"]["cache"]["hit"] is True
