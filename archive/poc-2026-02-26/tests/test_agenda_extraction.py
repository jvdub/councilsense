from __future__ import annotations


from minutes_spike.agenda import extract_agenda_items


def test_extract_agenda_items_includes_body_text_and_cuts_off_after_adjournment() -> None:
    text = (
        "1. CALL TO ORDER\n"
        "Mayor opened the meeting at 7:00 PM.\n\n"
        "2.A. ORDINANCE / PUBLIC HEARING - ZONING UPDATE\n"
        "Consideration of an ordinance to amend residential setback rules.\n"
        "Staff presented changes and recommended approval.\n\n"
        "3. ADJOURNMENT\n"
        "Meeting ended at 8:12 PM.\n\n"
        # Should be ignored (attachment-like numbered content after adjournment)
        "4.A. DEFINITIONS - FLOOR AREA RATIO\n"
        "This section defines floor area ratio for reference.\n"
    )

    items = extract_agenda_items(text)
    assert [i.item_id for i in items] == ["1", "2.A", "3"]
    assert items[0].title == "CALL TO ORDER"
    assert "Mayor opened the meeting" in items[0].body_text
    assert items[1].title == "ORDINANCE / PUBLIC HEARING - ZONING UPDATE"
    assert "amend residential setback rules" in items[1].body_text
    assert "Meeting ended" in items[2].body_text
