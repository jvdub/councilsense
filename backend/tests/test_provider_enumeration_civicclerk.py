from __future__ import annotations

import json

from councilsense.app.provider_enumeration import (
    CivicClerkSourceMeetingEnumerationProvider,
    enumerate_civicclerk_events,
)
from councilsense.db.city_registry import CitySourceConfig


def _build_source(*, source_url: str) -> CitySourceConfig:
    return CitySourceConfig(
        id="source-eagle-mountain-ut-minutes-primary",
        city_id="city-eagle-mountain-ut",
        source_type="minutes",
        source_url=source_url,
        parser_name="civicclerk-events-api",
        parser_version="v1",
        health_status="unknown",
        last_success_at=None,
        last_attempt_at=None,
        failure_streak=0,
        last_failure_at=None,
        last_failure_reason=None,
    )


def test_civicclerk_provider_enumerates_stable_normalized_meetings() -> None:
    payload = {
        "value": [
            {
                "id": 71,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-10T00:00:00Z",
                "publishedFiles": [
                    {"type": "Minutes", "name": "Minutes", "url": "stream/71-minutes.pdf"},
                    {"type": "Agenda", "name": "Agenda", "url": "stream/71-agenda.pdf"},
                ],
            },
            {
                "id": 70,
                "eventName": "City Council Work Session",
                "eventDate": "2026-03-03T00:00:00Z",
                "publishedFiles": [
                    {"type": "Agenda", "name": "Agenda", "url": "stream/70-agenda.pdf"}
                ],
            },
        ]
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/Events?" in url or "/events?" in url:
            return json.dumps(payload).encode("utf-8")
        if url == "https://eaglemountainut.portal.civicclerk.com/":
            return b"<html></html>"
        raise AssertionError(f"Unexpected URL fetched: {url}")

    source = _build_source(source_url="https://eaglemountainut.portal.civicclerk.com/")
    provider = CivicClerkSourceMeetingEnumerationProvider()

    meetings = provider.enumerate_meetings(source=source, timeout_seconds=5.0, fetch_url=_stub_fetch)

    assert [item.identity.source_meeting_id for item in meetings] == ["71", "70"]
    assert [item.title for item in meetings] == ["City Council Meeting", "City Council Work Session"]
    assert [item.body_name for item in meetings] == ["City Council", "City Council"]
    assert [item.meeting_date for item in meetings] == ["2026-03-10", "2026-03-03"]
    assert meetings[0].source_url == "https://eaglemountainut.portal.civicclerk.com/event/71/files"
    assert meetings[0].provider_metadata["published_document_kinds"] == ("minutes", "agenda")


def test_civicclerk_provider_normalizes_sparse_payloads_without_identity_churn() -> None:
    payload = {
        "value": [
            {
                "id": 88,
                "eventName": "City Council Special Session",
                "publishedFiles": [],
            }
        ]
    }

    def _stub_fetch(url: str, _: float) -> bytes:
        if "/Events?" in url or "/events?" in url:
            return json.dumps(payload).encode("utf-8")
        if url == "https://eaglemountainut.portal.civicclerk.com/":
            return b"<html></html>"
        raise AssertionError(f"Unexpected URL fetched: {url}")

    events = enumerate_civicclerk_events(
        source_url="https://eaglemountainut.portal.civicclerk.com/",
        timeout_seconds=5.0,
        fetch_url=_stub_fetch,
    )

    assert len(events) == 1
    assert events[0].source_meeting_id == "88"
    assert events[0].title == "City Council Special Session"
    assert events[0].meeting_date is None
    assert events[0].body_name == "City Council"
    assert events[0].provider_metadata["published_document_kinds"] == ()


def test_civicclerk_provider_is_deterministic_when_feeds_arrive_reordered() -> None:
    source_url = "https://eaglemountainut.portal.civicclerk.com/"
    feed_a = {
        "value": [
            {
                "id": 90,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-12T00:00:00Z",
                "publishedFiles": [
                    {"type": "Agenda", "name": "Agenda", "url": "stream/90-agenda.pdf"}
                ],
            },
            {
                "id": 89,
                "eventName": "City Council Meeting",
                "eventDate": "2026-03-05T00:00:00Z",
                "publishedFiles": [
                    {"type": "Minutes", "name": "Minutes", "url": "stream/89-minutes.pdf"}
                ],
            },
        ]
    }
    feed_b = {
        "value": [
            feed_a["value"][1],
            feed_a["value"][0],
        ]
    }

    def _stub_fetch_factory(primary_payload: dict[str, object], fallback_payload: dict[str, object]):
        def _stub_fetch(url: str, _: float) -> bytes:
            if "startDateTime+lt" in url:
                return json.dumps(primary_payload).encode("utf-8")
            if "startDateTime+ge" in url:
                return json.dumps(fallback_payload).encode("utf-8")
            if "/events?" in url or "/Events?" in url:
                return json.dumps(fallback_payload).encode("utf-8")
            if url == source_url:
                return b"<html></html>"
            raise AssertionError(f"Unexpected URL fetched: {url}")

        return _stub_fetch

    first = enumerate_civicclerk_events(
        source_url=source_url,
        timeout_seconds=5.0,
        fetch_url=_stub_fetch_factory(feed_a, feed_b),
    )
    second = enumerate_civicclerk_events(
        source_url=source_url,
        timeout_seconds=5.0,
        fetch_url=_stub_fetch_factory(feed_b, feed_a),
    )

    assert [item.source_meeting_id for item in first] == ["90", "89"]
    assert [item.source_meeting_id for item in second] == ["90", "89"]
    assert [(item.title, item.meeting_date, item.source_url) for item in first] == [
        (item.title, item.meeting_date, item.source_url) for item in second
    ]