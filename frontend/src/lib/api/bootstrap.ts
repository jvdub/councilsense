import { getApiBaseUrl } from "./baseUrl";

const RETRYABLE_STATUSES = new Set([502, 503, 504]);
const MAX_ATTEMPTS = 2;

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
  readonly retryable: boolean;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
    retryable = false,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

export async function fetchBootstrap(authToken: string): Promise<BootstrapResponse> {
  return fetchBootstrapJsonWithRetry<BootstrapResponse>(
    "/v1/me/bootstrap",
    authToken,
    "Failed to fetch bootstrap state",
  );
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
  const retryable = RETRYABLE_STATUSES.has(status);

  try {
    const payload = (await response.json()) as ApiErrorPayload;
    const message = payload.error?.message ?? fallbackMessage;
    const code = payload.error?.code ?? null;
    return new ApiError(message, status, code, retryable);
  } catch {
    return new ApiError(fallbackMessage, status, null, retryable);
  }
}

async function fetchBootstrapJsonWithRetry<T>(
  path: string,
  authToken: string,
  fallbackMessage: string,
): Promise<T> {
  let attempt = 0;

  while (attempt < MAX_ATTEMPTS) {
    try {
      const response = await fetch(`${getApiBaseUrl()}${path}`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
        cache: "no-store",
      });

      if (!response.ok) {
        const error = await parseApiError(response, fallbackMessage);

        if (error.retryable && attempt < MAX_ATTEMPTS - 1) {
          attempt += 1;
          continue;
        }

        throw error;
      }

      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }

      if (attempt >= MAX_ATTEMPTS - 1) {
        throw new ApiError(fallbackMessage, 0, null, false);
      }

      attempt += 1;
    }
  }

  throw new ApiError(fallbackMessage, 0, null, false);
}