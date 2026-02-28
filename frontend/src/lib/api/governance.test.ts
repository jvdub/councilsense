import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createDeletionRequest,
  createExportRequest,
  getDeletionRequest,
  getExportRequest,
  GovernanceApiError,
} from "./governance";

const fetchMock = vi.fn<typeof fetch>();

describe("governance api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates export request", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "export-1",
          status: "requested",
          scope: {
            include_profile: true,
            include_preferences: true,
            include_notification_history: true,
          },
          artifact_uri: null,
          error_code: null,
          completed_at: null,
          processing_attempt_count: 0,
          max_processing_attempts: 3,
          created_at: "2026-02-28T10:00:00Z",
          updated_at: "2026-02-28T10:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await createExportRequest("token-abc", { idempotency_key: "export-idem-1" });

    expect(result.id).toBe("export-1");
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/v1/me/exports", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer token-abc",
      },
      body: JSON.stringify({ idempotency_key: "export-idem-1" }),
    });
  });

  it("fetches export request status", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "export-1",
          status: "completed",
          scope: {
            include_profile: true,
            include_preferences: true,
            include_notification_history: true,
          },
          artifact_uri: "governance-export://export-1",
          error_code: null,
          completed_at: "2026-02-28T10:10:00Z",
          processing_attempt_count: 1,
          max_processing_attempts: 3,
          created_at: "2026-02-28T10:00:00Z",
          updated_at: "2026-02-28T10:10:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await getExportRequest("token-abc", "export-1");

    expect(result.status).toBe("completed");
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/v1/me/exports/export-1", {
      method: "GET",
      headers: {
        Authorization: "Bearer token-abc",
      },
      cache: "no-store",
    });
  });

  it("creates deletion request", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "deletion-1",
          status: "requested",
          mode: "anonymize",
          reason_code: "user_requested_account_deletion",
          due_at: "2026-03-30T10:00:00Z",
          completed_at: null,
          error_code: null,
          created_at: "2026-02-28T10:00:00Z",
          updated_at: "2026-02-28T10:00:00Z",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await createDeletionRequest("token-abc", {
      idempotency_key: "deletion-idem-1",
      mode: "anonymize",
      reason_code: "user_requested_account_deletion",
    });

    expect(result.id).toBe("deletion-1");
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/v1/me/deletions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer token-abc",
      },
      body: JSON.stringify({
        idempotency_key: "deletion-idem-1",
        mode: "anonymize",
        reason_code: "user_requested_account_deletion",
      }),
    });
  });

  it("fetches deletion request status", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "deletion-1",
          status: "accepted",
          mode: "delete",
          reason_code: "user_requested_account_deletion",
          due_at: "2026-03-30T10:00:00Z",
          completed_at: null,
          error_code: null,
          created_at: "2026-02-28T10:00:00Z",
          updated_at: "2026-02-28T10:05:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await getDeletionRequest("token-abc", "deletion-1");

    expect(result.status).toBe("accepted");
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/v1/me/deletions/deletion-1", {
      method: "GET",
      headers: {
        Authorization: "Bearer token-abc",
      },
      cache: "no-store",
    });
  });

  it("surfaces api error details", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "validation_error",
            message: "Invalid request",
          },
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(createExportRequest("token-abc", { idempotency_key: "" })).rejects.toMatchObject({
      message: "Invalid request",
      status: 422,
      code: "validation_error",
    });
  });

  it("falls back to default message when payload is not json", async () => {
    fetchMock.mockResolvedValueOnce(new Response("gateway timeout", { status: 504 }));

    let thrown: unknown;
    try {
      await getDeletionRequest("token-abc", "deletion-timeout");
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(GovernanceApiError);
    expect(thrown).toMatchObject({
      message: "Failed to fetch deletion request status",
      status: 504,
      code: null,
    });
  });
});
