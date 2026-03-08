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

function formatCityIdLabel(cityId: string): string {
  const trimmed = cityId.trim();

  if (!trimmed) {
    return cityId;
  }

  const withoutPrefix = trimmed.replace(/^city-/, "");
  const segments = withoutPrefix.split(/[_-]+/).filter((segment) => segment.length > 0);

  if (segments.length >= 2 && /^[a-z]{2}$/i.test(segments[segments.length - 1] ?? "")) {
    segments.pop();
  }

  if (segments.length === 0) {
    return humanizeIdentifier(trimmed, cityId);
  }

  return toTitleCase(segments.join(" "));
}

export function formatCityLabel(cityName: string | null | undefined, cityId: string): string {
  const trimmedName = cityName?.trim();

  if (trimmedName) {
    return trimmedName;
  }

  return formatCityIdLabel(cityId);
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

function buildResidentSectionLabel(value: string | null | undefined, fallbackKind?: string | null): string | null {
  const trimmed = value?.trim();

  if (!trimmed) {
    return fallbackKind ? humanizeIdentifier(fallbackKind) : null;
  }

  const sectionMatch = trimmed.match(/^([a-z]+)[/.]section[/.](.+)$/i);
  if (sectionMatch) {
    const [, documentKind, sectionValue] = sectionMatch;
    return `${humanizeIdentifier(documentKind)} section ${sectionValue.replace(/[._/-]+/g, " ")}`;
  }

  if (/^(artifact\.(html|pdf)|meeting\.metadata)$/i.test(trimmed)) {
    return fallbackKind ? `${humanizeIdentifier(fallbackKind)} document` : "Source document";
  }

  return humanizeIdentifier(trimmed);
}

function buildPageLabel(pageStart: number | null, pageEnd: number | null): string | null {
  if (pageStart === null) {
    return null;
  }

  if (pageEnd !== null && pageEnd !== pageStart) {
    return `pages ${pageStart}-${pageEnd}`;
  }

  return `page ${pageStart}`;
}

export function buildEvidenceLocator(pointer: {
  section_ref: string | null;
  char_start: number | null;
  char_end: number | null;
}): string {
  const parts: string[] = [];

  const residentSectionLabel = buildResidentSectionLabel(pointer.section_ref);
  if (residentSectionLabel) {
    parts.push(residentSectionLabel);
  }

  if (parts.length === 0) {
    return "Source document";
  }

  return parts.join(" • ");
}

export function buildTechnicalEvidenceLocator(pointer: {
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

export function buildEvidenceReferenceV2Locator(reference: {
  document_kind: string;
  section_path: string;
  page_start: number | null;
  page_end: number | null;
  char_start: number | null;
  char_end: number | null;
  precision: string;
}): string {
  const parts: string[] = [];

  const residentSectionLabel = buildResidentSectionLabel(
    reference.section_path,
    reference.document_kind,
  );
  if (residentSectionLabel) {
    parts.push(residentSectionLabel);
  }

  const pageLabel = buildPageLabel(reference.page_start, reference.page_end);
  if (pageLabel) {
    parts.push(pageLabel);
  }

  if (parts.length === 0) {
    return "Source document";
  }

  return parts.join(" • ");
}

export function buildTechnicalEvidenceReferenceV2Locator(reference: {
  section_path: string;
  page_start: number | null;
  page_end: number | null;
  char_start: number | null;
  char_end: number | null;
  precision: string;
}): string {
  const parts: string[] = [];

  if (reference.section_path.trim()) {
    parts.push(reference.section_path.trim());
  }

  const pageLabel = buildPageLabel(reference.page_start, reference.page_end);
  if (pageLabel) {
    parts.push(pageLabel);
  }

  if (reference.char_start !== null && reference.char_end !== null) {
    parts.push(`chars ${reference.char_start}-${reference.char_end}`);
  }

  if (reference.precision.trim()) {
    parts.push(`${humanizeIdentifier(reference.precision)} precision`);
  }

  if (parts.length === 0) {
    return "Locator unavailable";
  }

  return parts.join(" • ");
}