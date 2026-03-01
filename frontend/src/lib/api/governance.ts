import { getApiBaseUrl } from "./baseUrl";

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

export type ExportRequestScope = {
  include_profile: boolean;
  include_preferences: boolean;
  include_notification_history: boolean;
};

export type ExportRequestRecord = {
  id: string;
  status: string;
  scope: ExportRequestScope;
  artifact_uri: string | null;
  error_code: string | null;
  completed_at: string | null;
  processing_attempt_count: number;
  max_processing_attempts: number;
  created_at: string;
  updated_at: string;
};

export type CreateExportRequestPayload = {
  idempotency_key: string;
};

export type DeletionRequestMode = "delete" | "anonymize";

export type CreateDeletionRequestPayload = {
  idempotency_key: string;
  mode: DeletionRequestMode;
  reason_code?: string;
};

export type DeletionRequestRecord = {
  id: string;
  status: string;
  mode: DeletionRequestMode;
  reason_code: string | null;
  due_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  created_at: string;
  updated_at: string;
};

export class GovernanceApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function createExportRequest(
  authToken: string,
  payload: CreateExportRequestPayload,
): Promise<ExportRequestRecord> {
  const response = await fetch(`${getApiBaseUrl()}/v1/me/exports`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to create export request");
  }

  return (await response.json()) as ExportRequestRecord;
}

export async function getExportRequest(authToken: string, requestId: string): Promise<ExportRequestRecord> {
  const response = await fetch(`${getApiBaseUrl()}/v1/me/exports/${encodeURIComponent(requestId)}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${authToken}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to fetch export request status");
  }

  return (await response.json()) as ExportRequestRecord;
}

export async function createDeletionRequest(
  authToken: string,
  payload: CreateDeletionRequestPayload,
): Promise<DeletionRequestRecord> {
  const response = await fetch(`${getApiBaseUrl()}/v1/me/deletions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to create deletion request");
  }

  return (await response.json()) as DeletionRequestRecord;
}

export async function getDeletionRequest(authToken: string, requestId: string): Promise<DeletionRequestRecord> {
  const response = await fetch(`${getApiBaseUrl()}/v1/me/deletions/${encodeURIComponent(requestId)}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${authToken}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw await parseApiError(response, "Failed to fetch deletion request status");
  }

  return (await response.json()) as DeletionRequestRecord;
}

async function parseApiError(response: Response, fallbackMessage: string): Promise<GovernanceApiError> {
  const status = response.status;

  try {
    const payload = (await response.json()) as ApiErrorPayload;
    const message = payload.error?.message ?? fallbackMessage;
    const code = payload.error?.code ?? null;
    return new GovernanceApiError(message, status, code);
  } catch {
    return new GovernanceApiError(fallbackMessage, status);
  }
}