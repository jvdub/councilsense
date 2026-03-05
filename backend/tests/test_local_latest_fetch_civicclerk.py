from __future__ import annotations

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
        if url.endswith("/events"):
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
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert candidate.meeting_date_iso == "2026-03-01"
    assert candidate.candidate_url.endswith("stream/new-agenda.pdf")
    assert "Agenda" in candidate.title
    assert warning is None
