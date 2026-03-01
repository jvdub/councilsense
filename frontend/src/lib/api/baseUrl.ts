const DEFAULT_LOCAL_API_BASE_URL = "http://localhost:8000";
const DEFAULT_INTERNAL_API_BASE_URL = "http://api:8000";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_LOCAL_API_BASE_URL;
  }

  return (
    process.env.API_INTERNAL_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    DEFAULT_INTERNAL_API_BASE_URL
  );
}
