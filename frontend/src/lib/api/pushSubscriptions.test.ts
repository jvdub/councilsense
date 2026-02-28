import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createOrRefreshPushSubscription,
  deletePushSubscription,
  listPushSubscriptions,
  PushSubscriptionsApiError,
} from "./pushSubscriptions";

const fetchMock = vi.fn<typeof fetch>();

describe("push subscriptions api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists subscriptions from the current user endpoint", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "psub-1",
              endpoint: "https://example.test/push/sub-1",
              keys: { p256dh: "k1", auth: "a1" },
              status: "active",
              failure_reason: null,
              last_seen_at: "2026-02-27T12:00:00Z",
              created_at: "2026-02-27T12:00:00Z",
              updated_at: "2026-02-27T12:00:00Z",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await listPushSubscriptions("token-abc");

    expect(result.items).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/v1/me/push-subscriptions", {
      method: "GET",
      headers: {
        Authorization: "Bearer token-abc",
      },
      cache: "no-store",
    });
  });

  it("creates or refreshes subscription with endpoint and keys", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "psub-2",
          status: "active",
          failure_reason: null,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await createOrRefreshPushSubscription("token-abc", {
      endpoint: "https://example.test/push/sub-2",
      keys: {
        p256dh: "k2",
        auth: "a2",
      },
      user_agent: "test-agent",
    });

    expect(result).toEqual({
      id: "psub-2",
      status: "active",
      failure_reason: null,
    });
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/v1/me/push-subscriptions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer token-abc",
      },
      body: JSON.stringify({
        endpoint: "https://example.test/push/sub-2",
        keys: {
          p256dh: "k2",
          auth: "a2",
        },
        user_agent: "test-agent",
      }),
    });
  });

  it("deletes a subscription idempotently", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await deletePushSubscription("token-abc", "psub-3");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/v1/me/push-subscriptions/psub-3", {
      method: "DELETE",
      headers: {
        Authorization: "Bearer token-abc",
      },
    });
  });

  it("surfaces parsed API errors for deterministic recovery handling", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "validation_error",
            message: "endpoint is invalid",
            details: {
              endpoint: "https://example.test/push/sub-invalid",
            },
          },
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      createOrRefreshPushSubscription("token-abc", {
        endpoint: "https://example.test/push/sub-invalid",
        keys: {
          p256dh: "k-invalid",
          auth: "a-invalid",
        },
      }),
    ).rejects.toMatchObject({
      message: "endpoint is invalid",
      status: 422,
      code: "validation_error",
      details: {
        endpoint: "https://example.test/push/sub-invalid",
      },
    });
  });

  it("uses fallback typed errors when response body is not json", async () => {
    fetchMock.mockResolvedValueOnce(new Response("<html>error</html>", { status: 500 }));

    let thrown: unknown;
    try {
      await listPushSubscriptions("token-abc");
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(PushSubscriptionsApiError);
    expect(thrown).toMatchObject({
      message: "Failed to fetch push subscriptions",
      status: 500,
      code: null,
      details: null,
    });
  });
});