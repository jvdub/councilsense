from __future__ import annotations

from pathlib import Path

import pytest

from minutes_spike.chat import answer_question
from minutes_spike.store import import_meeting


def test_g2_ordinances_question_lists_items_and_cites_agenda_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    packet_text = (
        "1. CALL TO ORDER\nHello\n\n"
        "2. CONSENT AGENDA\nRoutine items.\n\n"
        "3.B. ORDINANCE / PUBLIC HEARING - ZONING TEXT AMENDMENT\n"
        "Proposal to amend city code Chapter 10.\n\n"
        "4.A. RESOLUTION - FEE SCHEDULE UPDATE\n"
        "Resolution to update fees.\n"
    )

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    resp = answer_question(
        store_dir=store_dir,
        meeting_id="2026-01-09",
        question="Which ordinances were on the agenda and what changed?",
    )

    assert resp["found"] is True
    assert "Ordinances/resolutions found" in (resp.get("answer") or "")
    assert "3.B" in (resp.get("answer") or "")

    ev = resp.get("evidence")
    assert isinstance(ev, list) and ev
    assert ev[0].get("bucket") == "agenda_item"
    assert isinstance(ev[0].get("agenda_item"), dict)


def test_g2_decided_about_laundromats_returns_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    packet_text = (
        "1. CALL TO ORDER\nHello\n\n"
        "2.C. CONDITIONAL USE PERMIT - NEW LAUNDROMAT\n"
        "Staff recommended approval. Motion to approve carried unanimously.\n"
    )

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    resp = answer_question(store_dir=store_dir, meeting_id="2026-01-09", question="What was decided about laundromats?")

    assert resp["found"] is True
    ev = resp.get("evidence")
    assert isinstance(ev, list) and ev
    assert ev[0].get("bucket") in {"agenda_item", "attachment", "meeting_text"}
    snip = (ev[0].get("snippet") or "").lower()
    assert "laundromat" in snip


def test_g2_related_to_sunset_flats_prefers_attachment_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    packet_text = (
        "1. CALL TO ORDER\nHello\n\n"
        "2.A. DISCUSSION - HOUSING\nGeneral discussion.\n\n"
        "ATTACHMENT 1: Staff Report\n"
        "Project: Sunset Flats\n"
        "This staff report mentions Sunset Flats as part of the proposal.\n"
    )

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    resp = answer_question(store_dir=store_dir, meeting_id="2026-01-09", question="What happened related to Sunset Flats?")

    assert resp["found"] is True
    ev = resp.get("evidence")
    assert isinstance(ev, list) and ev
    assert ev[0].get("bucket") == "attachment"


def test_g2_not_found_returns_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "Agenda Packet.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")

    packet_text = "1. CALL TO ORDER\nHello\n\n2. ADJOURNMENT\nBye\n"

    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", packet_text),
    )

    store_dir = tmp_path / "store"
    import_meeting(store_dir=store_dir, pdf_path=pdf_path, meeting_id="2026-01-09")

    resp = answer_question(store_dir=store_dir, meeting_id="2026-01-09", question="What was decided about spaceships?")
    assert resp["found"] is False
    assert str(resp.get("answer") or "").startswith("Not found")
