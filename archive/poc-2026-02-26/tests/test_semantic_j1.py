from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from minutes_spike import cli, llm


def test_j1_semantic_pass_rejects_laundry_room_false_positive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "m.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    # Rule is intentionally broad ("laundry") to simulate common false positive.
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        textwrap.dedent(
            """\
            rules:
              - id: laundromat
                description: New laundromats
                type: keyword_any
                enabled: true
                keywords: ["laundry"]
                min_hits: 1

            output:
              evidence:
                snippet_chars: 120
                max_snippets_per_rule: 3

            llm:
              provider: fake
              endpoint: http://fake
              model: fake-model
              timeout_s: 1
            """
        ),
        encoding="utf-8",
    )

    sample = (
        "1. CALL TO ORDER\n"
        "Mayor opened the meeting.\n\n"
        "2.C. DISCUSSION - BUILDING UPDATES\n"
        "The library will add a new laundry room for residents.\n\n"
    )
    monkeypatch.setattr(cli, "extract_pdf_text_canonical", lambda _path: ("pymupdf", sample))

    class _FakeProvider(llm.LLMProvider):
        def generate_text(self, *, prompt: str) -> str:
            # If the candidate text is about a "laundry room" (not a laundromat), reject.
            p = prompt.lower()
            candidate = p.split("candidate_text:", 1)[-1]
            if "laundry room" in candidate and "laundromat" not in candidate:
                return json.dumps(
                    {
                        "relevant": False,
                        "confidence": 0.85,
                        "why": "A laundry room is not a laundromat business or permit.",
                        "evidence": ["laundry room"],
                    }
                )
            return json.dumps(
                {
                    "relevant": True,
                    "confidence": 0.7,
                    "why": "Mentions laundromat.",
                    "evidence": ["laundromat"],
                }
            )

        def summarize_agenda_item(self, *, title: str, body_text: str) -> llm.SummaryResult:  # pragma: no cover
            raise AssertionError("summarize_agenda_item should not be used for J1")

    monkeypatch.setattr(cli, "create_llm_provider", lambda _cfg: _FakeProvider())

    out_path = tmp_path / "out.json"
    rc = cli.main(["--pdf", str(pdf_path), "--profile", str(profile_path), "--classify-relevance", "--out", str(out_path)])
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))

    # The broad keyword rule would match "laundry room", but semantic filter should reject it.
    things = payload.get("things_you_care_about")
    assert isinstance(things, list)
    assert things == []

    agenda_items = payload.get("agenda_items")
    assert isinstance(agenda_items, list) and agenda_items

    pb = None
    for it in agenda_items:
        if not isinstance(it, dict):
            continue
        pb_it = it.get("pass_b")
        if not isinstance(pb_it, dict):
            continue
        laund = pb_it.get("laundromat")
        if isinstance(laund, dict) and int(laund.get("hits", 0) or 0) > 0:
            pb = pb_it
            break
    assert isinstance(pb, dict)
    laund = pb.get("laundromat")
    assert isinstance(laund, dict)
    assert laund.get("relevant") is False
    sem = laund.get("semantic")
    assert isinstance(sem, dict)
    assert sem.get("relevant") is False
    assert isinstance((sem.get("provenance") or {}).get("prompt_template"), dict)
