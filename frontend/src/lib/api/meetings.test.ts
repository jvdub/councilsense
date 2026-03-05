import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchCityMeetings,
  fetchMeetingDetail,
  MeetingsApiError,
} from "./meetings";
import st022ContractFixtures from "./fixtures/st022_v1_contract_approval_fixtures.json";

const fetchMock = vi.fn<typeof fetch>();

describe("meetings api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches city meetings list with filters and preserves confidence values", async () => {
    const fixture = {
      items: [
        {
          id: "meeting-c",
          city_id: "salt-lake-city-ut",
          meeting_uid: "uid-c",
          title: "Meeting C",
          created_at: "2026-02-20 12:00:00",
          updated_at: "2026-02-20 12:00:00",
          status: "limited_confidence",
          confidence_label: "limited_confidence",
          reader_low_confidence: true,
        },
      ],
      next_cursor: "cursor-token",
      limit: 2,
    };

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(fixture), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchCityMeetings("token-123", "salt-lake-city-ut", {
      limit: 2,
      status: "processed",
      cursor: "cursor-a",
    });

    expect(result).toEqual(fixture);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/v1/cities/salt-lake-city-ut/meetings?cursor=cursor-a&limit=2&status=processed",
      {
        method: "GET",
        headers: {
          Authorization: "Bearer token-123",
        },
        cache: "no-store",
      },
    );
  });

  it("fetches meeting detail including evidence pointers contract shape", async () => {
    const nominalFixture = st022ContractFixtures.fixtures.find(
      (fixture) => fixture.fixture_id === "st022-nominal-multi-source",
    );
    expect(nominalFixture).toBeDefined();

    const fixture = {
      id: "meeting-detail-1",
      city_id: "salt-lake-city-ut",
      meeting_uid: "uid-detail-1",
      title: "Council Session",
      created_at: "2026-02-20 12:00:00",
      updated_at: "2026-02-20 12:00:00",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "pub-detail-1",
      published_at: "2026-02-20 13:00:00",
      summary: "Council approved the annual safety plan.",
      key_decisions: ["Approved annual safety plan"],
      key_actions: ["Staff to publish implementation memo"],
      notable_topics: ["Public safety", "Budget"],
      claims: [
        {
          id: "claim-detail-1",
          claim_order: 1,
          claim_text: "The council approved the annual safety plan.",
          evidence: [
            {
              id: "ptr-detail-1",
              artifact_id: "artifact-minutes-1",
              section_ref: "minutes.section.3",
              char_start: 100,
              char_end: 170,
              excerpt: "Council voted 6-1 to approve the annual safety plan.",
            },
          ],
        },
      ],
      planned: nominalFixture?.planned,
      outcomes: nominalFixture?.outcomes,
      planned_outcome_mismatches: nominalFixture?.planned_outcome_mismatches,
    };

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(fixture), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchMeetingDetail("token-abc", "meeting-detail-1");

    expect(result).toEqual(fixture);
    expect(result.claims[0]?.evidence[0]?.artifact_id).toBe("artifact-minutes-1");
    expect(result.planned?.source_coverage.packet).toBe("present");
    expect(result.outcomes?.authority_source).toBe("minutes");
    expect(result.planned_outcome_mismatches?.summary.total).toBe(1);
  });

  it("surfaces API error code/message/details for UI handling", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "not_found",
            message: "Meeting not found",
            details: { meeting_id: "missing-meeting-id" },
          },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(fetchMeetingDetail("token-abc", "missing-meeting-id")).rejects.toMatchObject({
      message: "Meeting not found",
      status: 404,
      code: "not_found",
      details: { meeting_id: "missing-meeting-id" },
      retryable: false,
    });
  });

  it("retries transient failures once and then returns parsed payload", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "temporarily_unavailable",
              message: "Try again",
            },
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [],
            next_cursor: null,
            limit: 20,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    const result = await fetchCityMeetings("token-retry", "salt-lake-city-ut");

    expect(result).toEqual({ items: [], next_cursor: null, limit: 20 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("falls back to explicit error type when body is not json", async () => {
    fetchMock.mockResolvedValueOnce(new Response("<html>Bad Gateway</html>", { status: 502 }));
    fetchMock.mockResolvedValueOnce(new Response("<html>Bad Gateway</html>", { status: 502 }));

    let thrown: unknown;
    try {
      await fetchCityMeetings("token-1", "salt-lake-city-ut");
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(MeetingsApiError);
    expect(thrown).toMatchObject({
      message: "Failed to fetch city meetings",
      status: 502,
      retryable: true,
    });
  });

  it("surfaces network failures as explicit typed errors", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Network request failed"));
    fetchMock.mockRejectedValueOnce(new TypeError("Network request failed"));

    await expect(fetchMeetingDetail("token-network", "meeting-1")).rejects.toMatchObject({
      message: "Failed to fetch meeting detail",
      status: 0,
      code: null,
      details: null,
      retryable: false,
    });
  });
});
