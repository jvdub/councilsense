const DEFAULT_LOCAL_API_BASE_URL = "http://localhost:8000";
const DEFAULT_INTERNAL_API_BASE_URL = "http://api:8000";
const DEFAULT_BROWSER_API_PORT = "8000";

function getBrowserDefaultApiBaseUrl(location: Pick<Location, "hostname" | "protocol">): string {
  if (!location.hostname || !/^https?:$/.test(location.protocol)) {
    return DEFAULT_LOCAL_API_BASE_URL;
  }

  return `${location.protocol}//${location.hostname}:${DEFAULT_BROWSER_API_PORT}`;
}

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_BASE_URL ?? getBrowserDefaultApiBaseUrl(window.location);
  }

  return (
    process.env.API_INTERNAL_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    DEFAULT_INTERNAL_API_BASE_URL
  );
}
