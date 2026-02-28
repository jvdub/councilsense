import {
  type ApiErrorPayload,
  type CityMeetingsListResponse,
  type MeetingDetailResponse,
  type MeetingListFilters,
} from "../models/meetings";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const RETRYABLE_STATUSES = new Set([502, 503, 504]);
const MAX_ATTEMPTS = 2;

export class MeetingsApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly details: Record<string, unknown> | null;
  readonly retryable: boolean;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
    details: Record<string, unknown> | null = null,
    retryable = false,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryable = retryable;
  }
}

export async function fetchCityMeetings(
  authToken: string,
  cityId: string,
  filters: MeetingListFilters = {},
): Promise<CityMeetingsListResponse> {
  const query = new URLSearchParams();

  if (filters.cursor !== undefined) {
    query.set("cursor", filters.cursor);
  }
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.status !== undefined) {
    query.set("status", filters.status);
  }

  const querySuffix = query.toString();
  const path = `/v1/cities/${encodeURIComponent(cityId)}/meetings${querySuffix ? `?${querySuffix}` : ""}`;

  return fetchJsonWithRetry<CityMeetingsListResponse>(
    path,
    authToken,
    "Failed to fetch city meetings",
  );
}

export async function fetchMeetingDetail(authToken: string, meetingId: string): Promise<MeetingDetailResponse> {
  const path = `/v1/meetings/${encodeURIComponent(meetingId)}`;
  return fetchJsonWithRetry<MeetingDetailResponse>(path, authToken, "Failed to fetch meeting detail");
}

async function fetchJsonWithRetry<T>(path: string, authToken: string, fallbackMessage: string): Promise<T> {
  let attempt = 0;

  while (attempt < MAX_ATTEMPTS) {
    try {
      const response = await fetch(`${API_BASE_URL}${path}`, {
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
      if (error instanceof MeetingsApiError) {
        throw error;
      }

      const canRetry = attempt < MAX_ATTEMPTS - 1;
      if (!canRetry) {
        throw new MeetingsApiError(fallbackMessage, 0, null, null, false);
      }

      attempt += 1;
    }
  }

  throw new MeetingsApiError(fallbackMessage, 0, null, null, false);
}

async function parseApiError(response: Response, fallbackMessage: string): Promise<MeetingsApiError> {
  const status = response.status;
  const retryable = RETRYABLE_STATUSES.has(status);

  try {
    const payload = (await response.json()) as ApiErrorPayload;
    const message = payload.error?.message ?? fallbackMessage;
    const code = payload.error?.code ?? null;
    const details = payload.error?.details ?? null;
    return new MeetingsApiError(message, status, code, details, retryable);
  } catch {
    return new MeetingsApiError(fallbackMessage, status, null, null, retryable);
  }
}
