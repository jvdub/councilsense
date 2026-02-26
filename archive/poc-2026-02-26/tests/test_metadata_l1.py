from __future__ import annotations

from minutes_spike.metadata import extract_meeting_metadata


def test_l1_extract_meeting_date_and_location_best_effort() -> None:
    text = (
        "CITY COUNCIL REGULAR MEETING\n"
        "January 23, 2026\n"
        "Location: City Hall Council Chambers\n"
        "123 Main Street\n"
        "\n"
        "1. CALL TO ORDER\n"
    )

    d, loc = extract_meeting_metadata(text)
    assert d == "2026-01-23"
    assert loc is not None
    assert "City Hall" in loc
