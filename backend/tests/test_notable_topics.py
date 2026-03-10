from __future__ import annotations

import sqlite3

from councilsense.app.notable_topics import sanitize_notable_topics
from councilsense.db.meetings import MeetingReadRepository


def test_sanitize_notable_topics_filters_low_signal_name_and_table_fragments() -> None:
    topics = (
        "Appointment Of Marcia Vasquez",
        "The Appointment",
        "Year Term",
        "Term Beginning",
        "Budget",
    )

    assert sanitize_notable_topics(topics) == ("Budget",)


def test_meeting_read_repository_sanitizes_stored_notable_topics() -> None:
    repository = MeetingReadRepository(sqlite3.connect(":memory:"))

    topics = repository._parse_notable_topic_list(
        '["Appointment Of Marcia Vasquez","Year Term","Board and Commission Appointments","Budget"]'
    )

    assert topics == ("Board and Commission Appointments", "Budget")


def test_sanitize_notable_topics_keeps_new_civic_summary_labels() -> None:
    topics = (
        "Legislative Update",
        "Quarterly Financial Report",
        "Land Use Planning",
        "Youth Council Code",
        "Project Change Orders",
    )

    assert sanitize_notable_topics(topics) == topics