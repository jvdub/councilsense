function toTitleCase(value: string): string {
  return value
    .split(" ")
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function normalizeDateInput(value: string | null | undefined): string | null {
  const trimmed = value?.trim();

  if (!trimmed) {
    return null;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return `${trimmed}T00:00:00`;
  }

  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(trimmed)) {
    return trimmed.replace(" ", "T");
  }

  return trimmed;
}

export function humanizeIdentifier(value: string | null | undefined, fallback = "Unknown"): string {
  const trimmed = value?.trim();

  if (!trimmed) {
    return fallback;
  }

  return toTitleCase(trimmed.replace(/[_-]+/g, " "));
}

export function formatCityLabel(cityName: string | null | undefined, cityId: string): string {
  const trimmedName = cityName?.trim();

  if (trimmedName) {
    return trimmedName;
  }

  return humanizeIdentifier(cityId, cityId);
}

export function formatCalendarDate(value: string | null | undefined, fallback = "Date unavailable"): string {
  const normalized = normalizeDateInput(value);

  if (!normalized) {
    return fallback;
  }

  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return fallback;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

export function formatTimestamp(value: string | null | undefined, fallback = "Unavailable"): string {
  const normalized = normalizeDateInput(value);

  if (!normalized) {
    return fallback;
  }

  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return fallback;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

export function formatSourceKindLabel(value: string | null | undefined): string {
  const trimmed = value?.trim();

  if (!trimmed) {
    return "Source document";
  }

  return `${humanizeIdentifier(trimmed)} source`;
}

export function buildEvidenceLocator(pointer: {
  section_ref: string | null;
  char_start: number | null;
  char_end: number | null;
}): string {
  const parts: string[] = [];

  if (pointer.section_ref?.trim()) {
    parts.push(pointer.section_ref.trim());
  }

  if (pointer.char_start !== null && pointer.char_end !== null) {
    parts.push(`chars ${pointer.char_start}-${pointer.char_end}`);
  }

  if (parts.length === 0) {
    return "Locator unavailable";
  }

  return parts.join(" • ");
}