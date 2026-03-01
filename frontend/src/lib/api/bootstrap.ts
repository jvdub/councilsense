import { getApiBaseUrl } from "./baseUrl";

export type BootstrapResponse = {
  user_id: string;
  home_city_id: string | null;
  onboarding_required: boolean;
  supported_city_ids: string[];
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

export async function fetchBootstrap(authToken: string): Promise<BootstrapResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/me/bootstrap`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${authToken}`
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to fetch bootstrap state");
  }

  return (await response.json()) as BootstrapResponse;
}

export async function submitHomeCitySelection(authToken: string, homeCityId: string): Promise<BootstrapResponse> {
  const response = await fetch(`${getApiBaseUrl()}/v1/me/bootstrap`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`
    },
    body: JSON.stringify({ home_city_id: homeCityId })
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to save home city");
  }

  return (await response.json()) as BootstrapResponse;
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