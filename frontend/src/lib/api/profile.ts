const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ProfileResponse = {
  email: string | null;
  home_city_id: string | null;
  notifications_enabled: boolean;
  notifications_paused_until: string | null;
};

export type PatchProfilePayload = {
  home_city_id?: string;
  notifications_enabled?: boolean;
  notifications_paused_until?: string | null;
};

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function fetchProfile(authToken: string): Promise<ProfileResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${authToken}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to fetch profile preferences");
  }

  return (await response.json()) as ProfileResponse;
}

export async function patchProfile(
  authToken: string,
  payload: PatchProfilePayload,
): Promise<ProfileResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/me`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to save profile preferences");
  }

  return (await response.json()) as ProfileResponse;
}

async function parseApiError(response: Response, fallbackMessage: string): Promise<ApiError> {
  const status = response.status;

  try {
    const payload = (await response.json()) as ApiErrorPayload;
    const message = payload.error?.message ?? fallbackMessage;
    const code = payload.error?.code ?? null;
    return new ApiError(message, status, code);
  } catch {
    return new ApiError(fallbackMessage, status);
  }
}