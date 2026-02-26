from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from minutes_spike import cli
from minutes_spike import llm
from minutes_spike.extract import PdfExtractionError
from minutes_spike.store import ImportedMeeting, IngestionError, generate_meeting_id, import_meeting
from minutes_spike.db import get_meeting, DB_FILENAME


def _write_fake_pdf(path: Path, content: bytes = b"%PDF-1.4\n%fake\n") -> None:
    path.write_bytes(content)


def test_generate_meeting_id_from_pdf_is_stable(tmp_path: Path) -> None:
    pdf_path = tmp_path / "m.pdf"
    data = b"%PDF-1.4\nhello\n"
    _write_fake_pdf(pdf_path, data)

    expected = hashlib.sha256(data).hexdigest()[:12]
    assert generate_meeting_id(pdf_path, None) == f"pdf_{expected}"


def test_import_meeting_writes_expected_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path)

    # Avoid depending on real PDF parsing libs/content.
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: (
            "pymupdf",
            "CITY COUNCIL REGULAR MEETING\nJanuary 23, 2026\nLocation: City Hall Council Chambers\n\n1. CALL TO ORDER\nHello world\n",
        ),
    )

    # Keep this test focused on import+metadata; don't couple to agenda/attachment heuristics.
    monkeypatch.setattr("minutes_spike.store.extract_agenda_items", lambda _text: [])
    monkeypatch.setattr("minutes_spike.store.extract_attachments", lambda _text, agenda_end=0: [])

    store_dir = tmp_path / "store"
    imported = import_meeting(store_dir=store_dir, pdf_path=pdf_path)

    assert isinstance(imported, ImportedMeeting)
    assert imported.meeting_dir.exists()
    assert (imported.meeting_dir / "source.pdf").exists()
    assert (imported.meeting_dir / "extracted_text.txt").exists()
    assert (imported.meeting_dir / "agenda_items.json").exists()
    assert (imported.meeting_dir / "attachments.json").exists()
    assert (imported.meeting_dir / "ingestion.json").exists()
    assert (imported.meeting_dir / "meeting.json").exists()

    ingestion = json.loads((imported.meeting_dir / "ingestion.json").read_text(encoding="utf-8"))
    assert ingestion["meeting_id"] == imported.meeting_id
    assert ingestion["inputs"]["pdf"]["sha256"]
    assert ingestion["artifacts"]["pdf_text"]["extractor"] == "pymupdf"
    assert ingestion["artifacts"]["agenda_items"]["stored_path"].endswith("agenda_items.json")

    meeting = json.loads((imported.meeting_dir / "meeting.json").read_text(encoding="utf-8"))
    assert meeting.get("meeting_date") == "2026-01-23"
    assert isinstance(meeting.get("meeting_location"), str)
    assert "City Hall" in str(meeting.get("meeting_location"))
    assert meeting["agenda_items"]["stored_path"].endswith("agenda_items.json")
    assert meeting["agenda_items"]["count"] == 0
    assert meeting["attachments"]["stored_path"].endswith("attachments.json")
    assert meeting["attachments"]["count"] == 0

    row = get_meeting(db_path=store_dir / DB_FILENAME, meeting_id=imported.meeting_id)
    assert row is not None
    assert row.meeting_date == "2026-01-23"
    assert row.meeting_location is not None
    assert "City Hall" in row.meeting_location


def test_import_meeting_scanned_pdf_raises_user_readable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path)

    def _raise(_path: Path):
        raise PdfExtractionError("PDF appears scanned or has no extractable text; OCR is not supported yet.")

    monkeypatch.setattr("minutes_spike.store.extract_pdf_text_canonical", _raise)

    with pytest.raises(IngestionError) as exc:
        import_meeting(store_dir=tmp_path / "store", pdf_path=pdf_path)

    assert "OCR is not supported yet" in str(exc.value)


def test_cli_generates_meeting_id_when_omitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    pdf_bytes = b"%PDF-1.4\nhello\n"
    _write_fake_pdf(pdf_path, pdf_bytes)

    # Minimal profile with zero rules.
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("rules: []\noutput: {evidence: {}}\n", encoding="utf-8")

    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", "Some text\n"))

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    expected_id = f"pdf_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"
    assert payload["meeting_id"] == expected_id


def test_cli_import_only_creates_meeting_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    pdf_bytes = b"%PDF-1.4\n%fake\n"
    _write_fake_pdf(pdf_path, pdf_bytes)

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("rules: []\noutput: {evidence: {}}\n", encoding="utf-8")

    # Patch the importer to avoid PDF parsing.
    def _fake_import(*, store_dir: Path, pdf_path: Path | None = None, text_path: Path | None = None, meeting_id: str | None = None):
        assert meeting_id is not None
        meeting_dir = store_dir / meeting_id
        meeting_dir.mkdir(parents=True, exist_ok=True)
        (meeting_dir / "source.pdf").write_bytes(b"x")
        (meeting_dir / "extracted_text.txt").write_text("t", encoding="utf-8")
        (meeting_dir / "ingestion.json").write_text("{}", encoding="utf-8")
        (meeting_dir / "meeting.json").write_text("{}", encoding="utf-8")
        return ImportedMeeting(
            meeting_id=meeting_id,
            meeting_dir=meeting_dir,
            meeting_json_path=meeting_dir / "meeting.json",
            ingestion_json_path=meeting_dir / "ingestion.json",
        )

    monkeypatch.setattr(cli, "import_meeting", _fake_import)

    store_dir = tmp_path / "store"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--store-dir",
            str(store_dir),
            "--import-only",
        ]
    )
    assert rc == 0
    expected_id = f"pdf_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"
    assert (store_dir / expected_id).exists()


def test_cli_agenda_out_writes_full_agenda_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text("rules: []\noutput: {evidence: {}}\n", encoding="utf-8")

    sample = (
        "1. CALL TO ORDER\n"
        "Mayor opened the meeting.\n\n"
        "2.A. DISCUSSION - PARKING UPDATES\n"
        "Staff presented changes.\n\n"
        "3. ADJOURNMENT\n"
        "Meeting ended.\n"
    )

    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    out_path = tmp_path / "out.json"
    agenda_out = tmp_path / "agenda_items.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--out",
            str(out_path),
            "--agenda-out",
            str(agenda_out),
        ]
    )
    assert rc == 0

    items = json.loads(agenda_out.read_text(encoding="utf-8"))
    assert [i["item_id"] for i in items] == ["1", "2.A", "3"]
    assert "body_text" in items[0]
    assert "start" in items[0]
    assert "end" in items[0]


def test_cli_summarize_first_item_adds_summary_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        "2.A. DISCUSSION - PARKING UPDATES\n"
        "Staff presented changes.\n\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            assert title
            assert body_text
            return llm.SummaryResult(bullets=["First bullet", "Second bullet"], raw_text="First bullet\nSecond bullet")

    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: _FakeProvider())

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--summarize-first-item",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["agenda_items"][0]["summary"] == ["First bullet", "Second bullet"]


def test_cli_summarize_first_item_error_sets_rc_and_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules: []\noutput: {evidence: {}}\nllm: {provider: ollama, endpoint: http://localhost:11434, model: fake, timeout_s: 1}\n",
        encoding="utf-8",
    )

    sample = "1. CALL TO ORDER\nMayor opened the meeting.\n"
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            raise llm.LLMError(
                code="llm_timeout",
                message="Timed out",
                retryable=True,
                provider="ollama",
                model="fake",
            )

    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: _FakeProvider())

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--summarize-first-item",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 2

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    err = payload["agenda_items"][0]["summary_error"]
    assert err["code"] == "llm_timeout"
    assert isinstance(payload["agenda_items"][0].get("summary"), list)


def test_cli_summarize_all_items_adds_pass_a_for_each_item(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        "2.A. DISCUSSION - PARKING UPDATES\n"
        "Staff presented changes and recommended approval.\n\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            self.calls.append((title, body_text))
            return llm.SummaryResult(bullets=[f"Summary for {title}"], raw_text=f"Summary for {title}")

    fake = _FakeProvider()
    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: fake)

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--summarize-all-items",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0
    assert len(fake.calls) == 2

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(payload["agenda_items"]) == 2
    for item in payload["agenda_items"]:
        assert isinstance(item.get("summary"), list)
        pass_a = item.get("pass_a")
        assert isinstance(pass_a, dict)
        assert isinstance(pass_a.get("summary"), list)
        assert isinstance(pass_a.get("citations"), list)
        # D1: must include at least one evidence quote/snippet.
        assert len(pass_a.get("citations") or []) >= 1


def test_cli_summarize_all_items_toon_roundtrip_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        "2.A. DISCUSSION - PARKING UPDATES\n"
        "Staff presented changes and recommended approval.\n\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def generate_text(self, *, prompt: str) -> str:
            assert "INPUT_TOON" in prompt
            return "summary:\n  - First\nactions:\n  - Approval requested\nkey_terms:\n  - parking\n"

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
            "--summarize-all-items",
            "--llm-use-toon",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(payload["agenda_items"]) == 2
    for item in payload["agenda_items"]:
        assert item["summary"] == ["First"]
        rt = item["llm_roundtrip"]
        assert rt["validated"] is True
        assert rt["output_json"]["summary"] == ["First"]


def test_cli_classify_relevance_adds_pass_b_and_things_you_care_about(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    # Profile with two interest rules.
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules:\n"
        "  - id: neighborhood_sunset_flats\n"
        "    description: Mentions Sunset Flats\n"
        "    type: keyword_any\n"
        "    enabled: true\n"
        "    keywords: [sunset flats]\n"
        "    min_hits: 1\n"
        "  - id: city_code_changes_residential\n"
        "    description: Code changes via ordinance\n"
        "    type: keyword_with_context\n"
        "    enabled: true\n"
        "    keywords: [ordinance]\n"
        "    context_keywords: [amend]\n"
        "    window_chars: 200\n"
        "    min_hits: 1\n"
        "output: {evidence: {snippet_chars: 120, max_snippets_per_rule: 3}}\n",
        encoding="utf-8",
    )

    sample = (
        "1. CONSENT AGENDA\n"
        "Approve minutes.\n\n"
        "2.A. ORDINANCE / PUBLIC HEARING - ZONING UPDATE\n"
        "Consideration of an ordinance to amend residential setback rules near Sunset Flats.\n\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--classify-relevance",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "things_you_care_about" in payload
    assert isinstance(payload["things_you_care_about"], list)
    assert len(payload["things_you_care_about"]) >= 1

    # Ensure pass_b exists per agenda item and why is only present with evidence.
    for item in payload["agenda_items"]:
        pb = item.get("pass_b")
        assert isinstance(pb, dict)
        for rule_id, rr in pb.items():
            assert "relevant" in rr
            if rr.get("relevant"):
                assert isinstance(rr.get("evidence"), list)
                assert len(rr.get("evidence") or []) >= 1
                assert isinstance(rr.get("why"), str)
            else:
                assert rr.get("why") is None


def test_cli_summarize_meeting_adds_meeting_summary_with_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules:\n"
        "  - id: neighborhood_sunset_flats\n"
        "    description: Mentions Sunset Flats\n"
        "    type: keyword_any\n"
        "    enabled: true\n"
        "    keywords: [sunset flats]\n"
        "    min_hits: 1\n"
        "output: {evidence: {snippet_chars: 120, max_snippets_per_rule: 3}}\n"
        "llm: {provider: ollama, endpoint: http://localhost:11434, model: fake, timeout_s: 1}\n",
        encoding="utf-8",
    )

    sample = (
        "1. ORDINANCE / PUBLIC HEARING - ZONING UPDATE\n"
        "Consideration of an ordinance to amend residential setback rules near Sunset Flats.\n\n"
        "2. OTHER BUSINESS\n"
        "General discussion.\n\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:
            return llm.SummaryResult(bullets=["Bullet"], raw_text="Bullet")

    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: _FakeProvider())

    out_path = tmp_path / "out.json"
    rc = cli.main(
        [
            "--pdf",
            str(pdf_path),
            "--profile",
            str(profile_path),
            "--summarize-all-items",
            "--classify-relevance",
            "--summarize-meeting",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    ms = payload.get("meeting_summary")
    assert isinstance(ms, dict)
    assert isinstance(ms.get("highlights"), list)
    assert len(ms.get("highlights") or []) >= 1
    # Evidence-first: every highlight must carry evidence.
    for h in ms["highlights"]:
        assert isinstance(h.get("evidence"), list)
        assert len(h.get("evidence") or []) >= 1
        assert isinstance((h["evidence"][0] or {}).get("snippet"), str)

    ors = ms.get("ordinances_resolutions")
    assert isinstance(ors, list)
    assert len(ors) >= 1
    assert ors[0]["kind"] in ("ordinance", "resolution")
    assert isinstance(ors[0].get("evidence"), list)
    assert len(ors[0].get("evidence") or []) >= 1


def test_cli_summarize_first_item_toon_roundtrip_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules: []\noutput: {evidence: {}}\nllm: {provider: ollama, endpoint: http://localhost:11434, model: fake, timeout_s: 1}\n",
        encoding="utf-8",
    )

    sample = "1. CALL TO ORDER\nMayor opened the meeting.\n"
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def generate_text(self, *, prompt: str) -> str:
            assert "INPUT_TOON" in prompt
            return "summary:\n  - First\n  - Second\nentities:\n  - Mayor\n"

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
    assert payload["agenda_items"][0]["summary"] == ["First", "Second"]
    rt = payload["agenda_items"][0]["llm_roundtrip"]
    assert rt["validated"] is True
    assert rt["output_json"]["entities"] == ["Mayor"]


def test_cli_summarize_first_item_toon_roundtrip_decode_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    _write_fake_pdf(pdf_path, b"%PDF-1.4\nhello\n")

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules: []\noutput: {evidence: {}}\nllm: {provider: ollama, endpoint: http://localhost:11434, model: fake, timeout_s: 1}\n",
        encoding="utf-8",
    )

    sample = "1. CALL TO ORDER\nMayor opened the meeting.\n"
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def generate_text(self, *, prompt: str) -> str:
            return "not_yaml: [\n"

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
    assert rc == 2

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    err = payload["agenda_items"][0]["summary_error"]
    assert err["code"] == "toon_decode_error"
    rt = payload["agenda_items"][0]["llm_roundtrip"]
    assert rt["validated"] is False
