from __future__ import annotations

from councilsense.api.routes.meetings import (
    CityMeetingCatalogListResponse,
    MeetingCatalogDiscoveredMeetingResponse,
    MeetingCatalogListItemResponse,
    MeetingCatalogProcessingStateResponse,
    MeetingProcessingRequestResponse,
)


def test_catalog_contract_supports_discovered_only_item() -> None:
    payload = CityMeetingCatalogListResponse(
        items=[
            MeetingCatalogListItemResponse(
                id="discovered-123",
                meeting_id=None,
                city_id="city-eagle-mountain-ut",
                city_name="Eagle Mountain",
                meeting_uid=None,
                title="City Council Work Session",
                created_at=None,
                updated_at=None,
                meeting_date="2026-03-14",
                body_name="City Council",
                status=None,
                confidence_label=None,
                reader_low_confidence=False,
                detail_available=False,
                discovered_meeting=MeetingCatalogDiscoveredMeetingResponse(
                    discovered_meeting_id="discovered-123",
                    source_meeting_id="71",
                    source_provider_name="civicclerk",
                    source_meeting_url="https://eaglemountainut.portal.civicclerk.com/event/71/files",
                    discovered_at="2026-03-10T20:00:00Z",
                    synced_at="2026-03-10T20:00:00Z",
                ),
                processing=MeetingCatalogProcessingStateResponse(
                    processing_status="discovered",
                    processing_status_updated_at="2026-03-10T20:00:00Z",
                ),
            )
        ],
        next_cursor=None,
        limit=20,
    ).model_dump(mode="json")

    item = payload["items"][0]
    assert item["meeting_id"] is None
    assert item["discovered_meeting"]["source_meeting_id"] == "71"
    assert item["processing"]["processing_status"] == "discovered"
    assert item["detail_available"] is False


def test_catalog_contract_supports_active_and_processed_items() -> None:
    queued = MeetingCatalogListItemResponse(
        id="discovered-queued",
        meeting_id=None,
        city_id="city-eagle-mountain-ut",
        city_name="Eagle Mountain",
        meeting_uid=None,
        title="City Council Meeting",
        created_at=None,
        updated_at=None,
        meeting_date="2026-03-20",
        body_name="City Council",
        status=None,
        confidence_label=None,
        reader_low_confidence=False,
        detail_available=False,
        discovered_meeting=MeetingCatalogDiscoveredMeetingResponse(
            discovered_meeting_id="discovered-queued",
            source_meeting_id="72",
            source_provider_name="civicclerk",
            source_meeting_url="https://eaglemountainut.portal.civicclerk.com/event/72/files",
            discovered_at="2026-03-11T09:00:00Z",
            synced_at="2026-03-11T09:00:00Z",
        ),
        processing=MeetingCatalogProcessingStateResponse(
            processing_status="queued",
            processing_status_updated_at="2026-03-11T09:01:00Z",
            processing_request_id="proc-req-72",
        ),
    )
    processed = MeetingCatalogListItemResponse(
        id="meeting-processed",
        meeting_id="meeting-processed",
        city_id="city-eagle-mountain-ut",
        city_name="Eagle Mountain",
        meeting_uid="uid-processed",
        title="City Council Meeting",
        created_at="2026-03-11T10:00:00Z",
        updated_at="2026-03-11T10:30:00Z",
        meeting_date="2026-03-20",
        body_name="City Council",
        status="processed",
        confidence_label="high",
        reader_low_confidence=False,
        detail_available=True,
        discovered_meeting=MeetingCatalogDiscoveredMeetingResponse(
            discovered_meeting_id="discovered-queued",
            source_meeting_id="72",
            source_provider_name="civicclerk",
            source_meeting_url="https://eaglemountainut.portal.civicclerk.com/event/72/files",
            discovered_at="2026-03-11T09:00:00Z",
            synced_at="2026-03-11T09:01:00Z",
        ),
        processing=MeetingCatalogProcessingStateResponse(
            processing_status="processed",
            processing_status_updated_at="2026-03-11T10:30:00Z",
        ),
    )
    failed = MeetingCatalogListItemResponse(
        id="discovered-failed",
        meeting_id=None,
        city_id="city-eagle-mountain-ut",
        city_name="Eagle Mountain",
        meeting_uid=None,
        title="Planning Commission",
        created_at=None,
        updated_at=None,
        meeting_date="2026-03-22",
        body_name="Planning Commission",
        status=None,
        confidence_label=None,
        reader_low_confidence=False,
        detail_available=False,
        discovered_meeting=MeetingCatalogDiscoveredMeetingResponse(
            discovered_meeting_id="discovered-failed",
            source_meeting_id="89",
            source_provider_name="civicclerk",
            source_meeting_url="https://eaglemountainut.portal.civicclerk.com/event/89/files",
            discovered_at="2026-03-11T11:00:00Z",
            synced_at="2026-03-11T11:00:00Z",
        ),
        processing=MeetingCatalogProcessingStateResponse(
            processing_status="failed",
            processing_status_updated_at="2026-03-11T11:05:00Z",
            processing_request_id="proc-req-89",
        ),
    )

    payload = CityMeetingCatalogListResponse(items=[queued, processed, failed], next_cursor="cursor-1", limit=3)
    serialized = payload.model_dump(mode="json")

    assert [item["processing"]["processing_status"] for item in serialized["items"]] == [
        "queued",
        "processed",
        "failed",
    ]
    assert serialized["items"][1]["status"] == "processed"
    assert serialized["items"][1]["detail_available"] is True
    assert serialized["items"][2]["meeting_id"] is None


def test_processing_request_contract_distinguishes_new_vs_existing_active_work() -> None:
    queued = MeetingProcessingRequestResponse(
        discovered_meeting_id="discovered-123",
        meeting_id=None,
        processing=MeetingCatalogProcessingStateResponse(
            processing_status="queued",
            processing_status_updated_at="2026-03-11T09:00:00Z",
            processing_request_id="proc-req-123",
            request_outcome="queued",
        ),
    ).model_dump(mode="json")
    already_active = MeetingProcessingRequestResponse(
        discovered_meeting_id="discovered-123",
        meeting_id=None,
        processing=MeetingCatalogProcessingStateResponse(
            processing_status="processing",
            processing_status_updated_at="2026-03-11T09:05:00Z",
            processing_request_id="proc-req-123",
            request_outcome="already_active",
        ),
    ).model_dump(mode="json")

    assert queued["processing"]["request_outcome"] == "queued"
    assert queued["processing"]["processing_status"] == "queued"
    assert already_active["processing"]["request_outcome"] == "already_active"
    assert already_active["processing"]["processing_status"] == "processing"