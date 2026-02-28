const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PushSubscriptionServerStatus = "active" | "invalid" | "expired" | "suppressed";

export type PushSubscriptionRecord = {
  id: string;
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
  status: PushSubscriptionServerStatus;
  failure_reason: string | null;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ListPushSubscriptionsResponse = {
  items: PushSubscriptionRecord[];
};

export type UpsertPushSubscriptionPayload = {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
  user_agent?: string;
  device_label?: string;
};

export type UpsertPushSubscriptionResponse = {
  id: string;
  status: PushSubscriptionServerStatus;
  failure_reason: string | null;
};

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

export class PushSubscriptionsApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly details: Record<string, unknown> | null;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
    details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function listPushSubscriptions(authToken: string): Promise<ListPushSubscriptionsResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/me/push-subscriptions`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${authToken}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to fetch push subscriptions");
  }

  return (await response.json()) as ListPushSubscriptionsResponse;
}

export async function createOrRefreshPushSubscription(
  authToken: string,
  payload: UpsertPushSubscriptionPayload,
): Promise<UpsertPushSubscriptionResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/me/push-subscriptions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to save push subscription");
  }

  return (await response.json()) as UpsertPushSubscriptionResponse;
}

export async function deletePushSubscription(authToken: string, subscriptionId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/v1/me/push-subscriptions/${encodeURIComponent(subscriptionId)}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    },
  );

  if (!response.ok) {
    throw await parseApiError(response, "Failed to delete push subscription");
  }
}

async function parseApiError(response: Response, fallbackMessage: string): Promise<PushSubscriptionsApiError> {
  const status = response.status;

  try {
    const payload = (await response.json()) as ApiErrorPayload;
    const message = payload.error?.message ?? fallbackMessage;
    const code = payload.error?.code ?? null;
    const details = payload.error?.details ?? null;
    return new PushSubscriptionsApiError(message, status, code, details);
  } catch {
    return new PushSubscriptionsApiError(fallbackMessage, status);
  }
}