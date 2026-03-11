from __future__ import annotations

import pytest

from councilsense.app.local_latest_fetch import _fetch_latest_candidate_from_civicclerk


def test_civicclerk_selects_latest_event_then_prefers_minutes() -> None:
    payload = {
        "value": [
            {
                "id": 1,
                "eventName": "City Council Meeting",
                "eventDate": "2025-12-01T00:00:00Z",
                "publishedFiles": [
                    {"type": "Minutes", "name": "Minutes Old", "url": "stream/old-minutes.pdf"}
                ],
            },
            {
                "id": 2,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-01T00:00:00Z",
                "publishedFiles": [
                    {"type": "Agenda", "name": "Agenda New", "url": "stream/new-agenda.pdf"}
                ],
            },
        ]
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/events?" in url or url.endswith("/events"):
            import json

            return json.dumps(payload).encode("utf-8")
        if "GetMeetingFile(" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/minutes.txt"}'
        if "GetMeetingFile(" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/minutes.pdf"}'
        if url.endswith("minutes.txt"):
            return b"Text transcript for meeting minutes"
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, _, _, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        preferred_file_type="minutes",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2025-12-01"
    assert candidate.candidate_url.endswith("stream/old-minutes.pdf")
    assert "Minutes" in candidate.title
    assert warning is None


def test_civicclerk_prefers_agenda_for_agenda_source_when_both_are_published() -> None:
    payload = {
        "value": [
            {
                "id": 12,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-03T00:00:00Z",
                "publishedFiles": [
                    {
                        "type": "Minutes",
                        "name": "Approved Minutes",
                        "url": "stream/new-minutes.pdf",
                    },
                    {
                        "type": "Agenda",
                        "name": "Agenda",
                        "url": "stream/new-agenda.pdf",
                    },
                ],
            }
        ]
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/events?" in url:
            import json

            return json.dumps(payload).encode("utf-8")
        if "GetMeetingFile(" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/agenda.txt"}'
        if "GetMeetingFile(" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/agenda.pdf"}'
        if url.endswith("agenda.txt"):
            return b"Agenda plain text"
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, _, _, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        preferred_file_type="agenda",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-03"
    assert "Agenda" in candidate.title
    assert warning is None


def test_civicclerk_event_url_uses_explicit_event_id_and_meetings_endpoint() -> None:
    event_payload = {
        "id": 710,
        "eventName": "City Council Meeting",
        "eventDate": "2026-03-03T00:00:00Z",
        "agendaId": 480,
    }
    meeting_payload = {
        "id": 480,
        "publishedFiles": [
            {
                "type": "Agenda",
                "name": "Agenda",
                "fileId": 1680,
                "url": "Meetings/GetMeetingFile(fileId=1680,plainText=false)",
            }
        ],
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if url.endswith("/Events/710"):
            import json

            return json.dumps(event_payload).encode("utf-8")
        if url.endswith("/Meetings/480"):
            import json

            return json.dumps(meeting_payload).encode("utf-8")
        if "GetMeetingFile(" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/agenda-710.txt"}'
        if "GetMeetingFile(" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/agenda-710.pdf"}'
        if url.endswith("agenda-710.txt"):
            return b"March 3, 2026 city council agenda text"
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, artifact_bytes, artifact_suffix, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/event/710/files",
        preferred_file_type="agenda",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-03"
    assert "Agenda" in candidate.title
    assert artifact_suffix == ".txt"
    assert b"March 3, 2026" in artifact_bytes
    assert warning is None


def test_civicclerk_minutes_source_fails_for_explicit_event_without_minutes() -> None:
    event_payload = {
        "id": 710,
        "eventName": "City Council Meeting",
        "eventDate": "2026-03-03T00:00:00Z",
        "agendaId": 480,
    }
    meeting_payload = {
        "id": 480,
        "publishedFiles": [
            {
                "type": "Agenda",
                "name": "Agenda",
                "fileId": 1680,
                "url": "Meetings/GetMeetingFile(fileId=1680,plainText=false)",
            }
        ],
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if url.endswith("/Events/710"):
            import json

            return json.dumps(event_payload).encode("utf-8")
        if url.endswith("/Meetings/480"):
            import json

            return json.dumps(meeting_payload).encode("utf-8")
        raise AssertionError(f"Unexpected URL fetched: {url}")

    with pytest.raises(Exception, match="No published minutes, agenda, or packet file was found"):
        _fetch_latest_candidate_from_civicclerk(
            source_url="https://eaglemountainut.portal.civicclerk.com/event/710/files",
            preferred_file_type="minutes",
            timeout_seconds=5.0,
            fetch_url=_stub_fetch,
        )


def test_civicclerk_skips_newest_event_without_published_files() -> None:
    payload = {
        "value": [
            {
                "id": 20,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-05T00:00:00Z",
                "publishedFiles": [],
            },
            {
                "id": 19,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-03T00:00:00Z",
                "publishedFiles": [
                    {
                        "type": "Agenda",
                        "name": "Agenda",
                        "url": "stream/mar-3-agenda.pdf",
                    }
                ],
            },
        ]
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/events?" in url:
            import json

            return json.dumps(payload).encode("utf-8")
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, _, _, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        preferred_file_type="agenda",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-03"
    assert candidate.candidate_url.endswith("stream/mar-3-agenda.pdf")
    assert warning is None


def test_civicclerk_supports_latest_offset_for_completed_events() -> None:
    payload = {
        "value": [
            {
                "id": 21,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-09T00:00:00Z",
                "publishedFiles": [
                    {
                        "type": "Minutes",
                        "name": "Minutes March 9",
                        "url": "stream/mar-9-minutes.pdf",
                    }
                ],
            },
            {
                "id": 20,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-03T00:00:00Z",
                "publishedFiles": [
                    {
                        "type": "Minutes",
                        "name": "Minutes March 3",
                        "url": "stream/mar-3-minutes.pdf",
                    }
                ],
            },
        ]
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/events?" in url or url.endswith("/events"):
            import json

            return json.dumps(payload).encode("utf-8")
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, _, _, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        preferred_file_type="minutes",
        latest_offset=1,
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-03"
    assert candidate.candidate_url.endswith("stream/mar-3-minutes.pdf")
    assert warning is None


def test_civicclerk_uses_portal_event_ids_when_events_feed_is_stale() -> None:
    stale_payload = {
        "value": [
            {
                "id": 146,
                "eventName": "City Council Meeting",
                "eventDate": "2024-12-03T00:00:00Z",
                "publishedFiles": [
                    {
                        "type": "Minutes",
                        "name": "Minutes",
                        "url": "stream/old-minutes.pdf",
                    }
                ],
            }
        ]
    }
    event_710 = {
        "id": 710,
        "eventName": "City Council Meeting",
        "eventDate": "2026-03-03T00:00:00Z",
        "agendaId": 480,
    }
    meeting_480 = {
        "id": 480,
        "publishedFiles": [
            {
                "type": "Agenda",
                "name": "Agenda",
                "fileId": 1680,
                "url": "Meetings/GetMeetingFile(fileId=1680,plainText=false)",
            }
        ],
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/events?" in url:
            import json

            return json.dumps(stale_payload).encode("utf-8")
        if url == "https://eaglemountainut.portal.civicclerk.com/":
            return b'<a href="/event/710/files">Go To Event Media</a>'
        if url.endswith("/Events/710"):
            import json

            return json.dumps(event_710).encode("utf-8")
        if url.endswith("/Meetings/480"):
            import json

            return json.dumps(meeting_480).encode("utf-8")
        if "GetMeetingFile(" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/agenda-710.txt"}'
        if "GetMeetingFile(" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/agenda-710.pdf"}'
        if url.endswith("agenda-710.txt"):
            return b"City Council March 3, 2026 agenda"
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, _, _, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        preferred_file_type="agenda",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-03"
    assert "Agenda" in candidate.title
    assert warning is None


def test_civicclerk_enrichment_prefers_meeting_published_files_over_event_payload() -> None:
    stale_feed = {
        "value": [
            {
                "id": 710,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-03T00:00:00Z",
                "agendaId": 480,
                "publishedFiles": [
                    {
                        "type": "Minutes",
                        "name": "Stale Minutes",
                        "url": "stream/old-minutes.pdf",
                    }
                ],
            }
        ]
    }
    meeting_480 = {
        "id": 480,
        "publishedFiles": [
            {
                "type": "Agenda",
                "name": "Agenda",
                "fileId": 1680,
                "url": "Meetings/GetMeetingFile(fileId=1680,plainText=false)",
            }
        ],
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/events?" in url:
            import json

            return json.dumps(stale_feed).encode("utf-8")
        if url.endswith("/Meetings/480"):
            import json

            return json.dumps(meeting_480).encode("utf-8")
        if "GetMeetingFile(" in url and "plainText=true" in url:
            return b'{"blobUri":"https://blob.example/agenda-710.txt"}'
        if "GetMeetingFile(" in url and "plainText=false" in url:
            return b'{"blobUri":"https://blob.example/agenda-710.pdf"}'
        if url.endswith("agenda-710.txt"):
            return b"March 3, 2026 agenda text"
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, artifact_bytes, artifact_suffix, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        preferred_file_type="agenda",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-03"
    assert "Agenda" in candidate.title
    assert artifact_suffix == ".txt"
    assert b"March 3, 2026" in artifact_bytes
    assert warning is None


def test_civicclerk_prefers_latest_completed_event_when_future_event_is_only_one_available() -> None:
    payload = {
        "value": [
            {
                "id": 801,
                "eventName": "City Council Meeting",
                "eventDate": "2099-03-05T00:00:00Z",
                "publishedFiles": [
                    {
                        "type": "Agenda",
                        "name": "Future Agenda",
                        "url": "stream/future-agenda.pdf",
                    }
                ],
            },
            {
                "id": 710,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-03T00:00:00Z",
                "publishedFiles": [
                    {
                        "type": "Agenda",
                        "name": "Completed Agenda",
                        "url": "stream/completed-agenda.pdf",
                    }
                ],
            },
        ]
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/events?" in url:
            import json

            return json.dumps(payload).encode("utf-8")
        return b"%PDF-1.7\nmock pdf bytes"

    candidate, _, _, warning = _fetch_latest_candidate_from_civicclerk(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        preferred_file_type="agenda",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-03"
    assert candidate.candidate_url.endswith("stream/completed-agenda.pdf")
    assert warning is None
