from __future__ import annotations

from minutes_spike.attachments import extract_attachments


def test_extract_attachments_detects_exhibit_and_type_plat() -> None:
    text = (
        "1. CALL TO ORDER\n"
        "2. ADJOURNMENT\n\n"
        "EXHIBIT A: PLAT - SUNSET FLATS PHASE 'A'\n"
        "LEGAL DESCRIPTION\n"
        "Township 1 South Range 1 East Salt Lake Base and Meridian\n"
        "Some more plat text.\n\n"
        "EXHIBIT B - STAFF REPORT\n"
        "Staff Report\n"
        "Recommendation: approve.\n"
    )

    # agenda_end after adjournment line; keep it simple
    agenda_end = text.find("EXHIBIT")
    attachments = extract_attachments(text, agenda_end=agenda_end)

    assert len(attachments) == 2
    assert attachments[0].attachment_id.upper().startswith("EXHIBIT_")
    assert "EXHIBIT" in attachments[0].title.upper()
    assert attachments[0].type_guess == "plat"
    assert "Township" in attachments[0].body_text

    assert attachments[1].type_guess == "staff_report"
    assert "Recommendation" in attachments[1].body_text


def test_extract_attachments_returns_empty_when_no_markers() -> None:
    text = "1. CALL TO ORDER\nHello\n2. ADJOURNMENT\nBye\n"
    attachments = extract_attachments(text, agenda_end=len(text))
    assert attachments == []
