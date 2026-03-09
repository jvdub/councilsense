import {
  type MeetingDetailResponse,
  type MeetingEvidenceReferenceV2,
  type MeetingOutcomeItem,
  type MeetingPlannedItem,
  type MeetingStructuredRelevance,
  type MeetingStructuredRelevanceConfidence,
  type MeetingStructuredRelevanceField,
  type MeetingStructuredRelevanceImpactTag,
} from "../models/meetings";

export const MEETING_DETAIL_RESIDENT_SCAN_FLAG =
  "NEXT_PUBLIC_ST034_UI_RESIDENT_SCAN_ENABLED";

const RESIDENT_SCAN_IMPACT_TAG_ORDER = {
  housing: 0,
  traffic: 1,
  utilities: 2,
  parks: 3,
  fees: 4,
  land_use: 5,
} as const;

type ApprovedImpactTag = keyof typeof RESIDENT_SCAN_IMPACT_TAG_ORDER;
type UnknownRecord = Record<string, unknown>;

export type MeetingResidentScanRenderMode = "baseline" | "resident_scan";

export type MeetingResidentScanFeatureFlags = {
  residentScanEnabled: boolean;
};

export type MeetingResidentScanBlockContractState =
  | "present"
  | "missing"
  | "invalid";

export type MeetingResidentScanCardsContractState =
  | "present"
  | "partial"
  | "missing";

export type MeetingResidentScanFallbackReason =
  | "resident_scan_flag_disabled"
  | "missing_structured_relevance"
  | "invalid_structured_relevance";

export type MeetingResidentScanFieldKey =
  | "subject"
  | "location"
  | "action"
  | "scale";

export type MeetingResidentScanFieldState = "present" | "missing";

export type MeetingResidentScanFieldModel = {
  key: MeetingResidentScanFieldKey;
  label: string;
  state: MeetingResidentScanFieldState;
  value: string | null;
  confidence: MeetingStructuredRelevanceConfidence | null;
  evidenceReferences: MeetingEvidenceReferenceV2[];
};

export type MeetingResidentScanImpactTagModel = {
  tag: ApprovedImpactTag;
  confidence: MeetingStructuredRelevanceConfidence | null;
  evidenceReferences: MeetingEvidenceReferenceV2[];
};

export type MeetingResidentScanCardSource = "meeting" | "planned" | "outcome";

export type MeetingResidentScanCardState = "complete" | "partial";

export type MeetingResidentScanCardModel = {
  id: string;
  source: MeetingResidentScanCardSource;
  sourceItemId: string | null;
  title: string;
  state: MeetingResidentScanCardState;
  fields: Record<MeetingResidentScanFieldKey, MeetingResidentScanFieldModel>;
  impactTags: MeetingResidentScanImpactTagModel[];
};

export type MeetingResidentScanResolvedRenderState = {
  mode: MeetingResidentScanRenderMode;
  modeFallbackReason: MeetingResidentScanFallbackReason | null;
  flags: MeetingResidentScanFeatureFlags;
  contract: {
    structuredRelevance: MeetingResidentScanBlockContractState;
    cards: MeetingResidentScanCardsContractState;
  };
  cards: MeetingResidentScanCardModel[];
};

export function getMeetingResidentScanFeatureFlags(
  env: NodeJS.ProcessEnv = process.env,
): MeetingResidentScanFeatureFlags {
  return {
    residentScanEnabled: env[MEETING_DETAIL_RESIDENT_SCAN_FLAG] === "true",
  };
}

export function resolveMeetingResidentScanRenderState(
  detail: MeetingDetailResponse,
  flags: MeetingResidentScanFeatureFlags,
): MeetingResidentScanResolvedRenderState {
  const structuredRelevance = classifyStructuredRelevanceBlock(
    detail.structured_relevance,
  );

  if (!flags.residentScanEnabled) {
    return {
      mode: "baseline",
      modeFallbackReason: "resident_scan_flag_disabled",
      flags,
      contract: {
        structuredRelevance,
        cards: "missing",
      },
      cards: [],
    };
  }

  if (structuredRelevance === "missing") {
    return {
      mode: "baseline",
      modeFallbackReason: "missing_structured_relevance",
      flags,
      contract: {
        structuredRelevance,
        cards: "missing",
      },
      cards: [],
    };
  }

  if (structuredRelevance === "invalid") {
    return {
      mode: "baseline",
      modeFallbackReason: "invalid_structured_relevance",
      flags,
      contract: {
        structuredRelevance,
        cards: "missing",
      },
      cards: [],
    };
  }

  const cards = buildMeetingResidentScanCardModels(detail);

  return {
    mode: "resident_scan",
    modeFallbackReason: null,
    flags,
    contract: {
      structuredRelevance,
      cards: classifyCardsContract(cards),
    },
    cards,
  };
}

export function buildMeetingResidentScanCardModels(
  detail: MeetingDetailResponse,
): MeetingResidentScanCardModel[] {
  const meetingRelevance = normalizeStructuredRelevance(detail.structured_relevance);
  if (meetingRelevance === null) {
    return [];
  }

  const outcomeCards = (detail.outcomes?.items ?? [])
    .map((item) => buildOutcomeCard(item))
    .filter((item): item is MeetingResidentScanCardModel => item !== null);
  if (outcomeCards.length > 0) {
    return outcomeCards;
  }

  const plannedCards = (detail.planned?.items ?? [])
    .map((item) => buildPlannedCard(item))
    .filter((item): item is MeetingResidentScanCardModel => item !== null);
  if (plannedCards.length > 0) {
    return plannedCards;
  }

  return [buildMeetingSummaryCard(detail.title, meetingRelevance)];
}

function classifyStructuredRelevanceBlock(
  value: unknown,
): MeetingResidentScanBlockContractState {
  if (value === undefined) {
    return "missing";
  }

  return normalizeStructuredRelevance(value) === null ? "invalid" : "present";
}

function classifyCardsContract(
  cards: MeetingResidentScanCardModel[],
): MeetingResidentScanCardsContractState {
  if (cards.length === 0) {
    return "missing";
  }

  return cards.some((card) => card.state === "partial") ? "partial" : "present";
}

function buildMeetingSummaryCard(
  fallbackTitle: string,
  relevance: MeetingStructuredRelevance,
): MeetingResidentScanCardModel {
  return buildCardModel({
    id: "meeting:summary",
    source: "meeting",
    sourceItemId: null,
    fallbackTitle,
    relevance,
  });
}

function buildPlannedCard(item: MeetingPlannedItem): MeetingResidentScanCardModel | null {
  const relevance = normalizeStructuredRelevance(item);
  if (relevance === null) {
    return null;
  }

  return buildCardModel({
    id: `planned:${item.planned_id}`,
    source: "planned",
    sourceItemId: item.planned_id,
    fallbackTitle: item.title,
    relevance,
  });
}

function buildOutcomeCard(item: MeetingOutcomeItem): MeetingResidentScanCardModel | null {
  const relevance = normalizeStructuredRelevance(item);
  if (relevance === null) {
    return null;
  }

  return buildCardModel({
    id: `outcome:${item.outcome_id}`,
    source: "outcome",
    sourceItemId: item.outcome_id,
    fallbackTitle: item.title,
    relevance,
  });
}

function buildCardModel({
  id,
  source,
  sourceItemId,
  fallbackTitle,
  relevance,
}: {
  id: string;
  source: MeetingResidentScanCardSource;
  sourceItemId: string | null;
  fallbackTitle: string;
  relevance: MeetingStructuredRelevance;
}): MeetingResidentScanCardModel {
  const fields = {
    subject: buildFieldModel("subject", relevance.subject),
    location: buildFieldModel("location", relevance.location),
    action: buildFieldModel("action", relevance.action),
    scale: buildFieldModel("scale", relevance.scale),
  };
  const impactTags = buildImpactTagModels(relevance.impact_tags);
  const presentFieldCount = Object.values(fields).filter(
    (field) => field.state === "present",
  ).length;

  return {
    id,
    source,
    sourceItemId,
    title: fields.subject.value ?? fallbackTitle,
    state: presentFieldCount === 4 ? "complete" : "partial",
    fields,
    impactTags,
  };
}

function buildFieldModel(
  key: MeetingResidentScanFieldKey,
  value: MeetingStructuredRelevanceField | undefined,
): MeetingResidentScanFieldModel {
  return {
    key,
    label: getFieldLabel(key),
    state: value ? "present" : "missing",
    value: value?.value ?? null,
    confidence: value?.confidence ?? null,
    evidenceReferences: value?.evidence_references_v2 ?? [],
  };
}

function getFieldLabel(key: MeetingResidentScanFieldKey): string {
  switch (key) {
    case "subject":
      return "What";
    case "location":
      return "Where";
    case "action":
      return "Action";
    case "scale":
      return "Scale";
  }
}

function normalizeStructuredRelevance(
  value: unknown,
): MeetingStructuredRelevance | null {
  if (!isRecord(value)) {
    return null;
  }

  const subject = normalizeStructuredField(value.subject);
  const location = normalizeStructuredField(value.location);
  const action = normalizeStructuredField(value.action);
  const scale = normalizeStructuredField(value.scale);
  const impactTags = normalizeStructuredImpactTags(value.impact_tags);

  if (
    subject === null &&
    location === null &&
    action === null &&
    scale === null &&
    impactTags.length === 0
  ) {
    return null;
  }

  return {
    ...(subject ? { subject } : {}),
    ...(location ? { location } : {}),
    ...(action ? { action } : {}),
    ...(scale ? { scale } : {}),
    ...(impactTags.length > 0 ? { impact_tags: impactTags } : {}),
  };
}

function normalizeStructuredField(
  value: unknown,
): MeetingStructuredRelevanceField | null {
  if (!isRecord(value) || typeof value.value !== "string") {
    return null;
  }

  const normalizedValue = value.value.trim();
  if (!normalizedValue) {
    return null;
  }

  const confidence = normalizeConfidence(value.confidence);
  const evidenceReferences = normalizeEvidenceReferences(
    value.evidence_references_v2,
  );

  return {
    value: normalizedValue,
    ...(confidence ? { confidence } : {}),
    ...(evidenceReferences.length > 0
      ? { evidence_references_v2: evidenceReferences }
      : {}),
  };
}

function normalizeImpactTags(
  value: unknown,
): MeetingResidentScanImpactTagModel[] {
  return buildImpactTagModels(normalizeStructuredImpactTags(value));
}

function buildImpactTagModels(
  tags: MeetingStructuredRelevanceImpactTag[] | undefined,
): MeetingResidentScanImpactTagModel[] {
  if (!tags) {
    return [];
  }

  return tags.map((tag) => ({
    tag: tag.tag,
    confidence: tag.confidence ?? null,
    evidenceReferences: tag.evidence_references_v2 ?? [],
  }));
}

function normalizeStructuredImpactTags(
  value: unknown,
): MeetingStructuredRelevanceImpactTag[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const deduped = new Map<ApprovedImpactTag, MeetingStructuredRelevanceImpactTag>();
  for (const item of value) {
    const tag = normalizeImpactTag(item);
    if (tag && !deduped.has(tag.tag)) {
      deduped.set(tag.tag, tag);
    }
  }

  return [...deduped.values()].sort(
    (left, right) =>
      RESIDENT_SCAN_IMPACT_TAG_ORDER[left.tag] -
      RESIDENT_SCAN_IMPACT_TAG_ORDER[right.tag],
  );
}

function normalizeImpactTag(
  value: unknown,
): MeetingStructuredRelevanceImpactTag | null {
  if (!isRecord(value) || typeof value.tag !== "string") {
    return null;
  }

  const normalizedTag = value.tag.trim().toLowerCase();
  if (!(normalizedTag in RESIDENT_SCAN_IMPACT_TAG_ORDER)) {
    return null;
  }

  const confidence = normalizeConfidence(value.confidence);
  const evidenceReferences = normalizeEvidenceReferences(
    value.evidence_references_v2,
  );

  return {
    tag: normalizedTag as ApprovedImpactTag,
    ...(confidence ? { confidence } : {}),
    ...(evidenceReferences.length > 0
      ? { evidence_references_v2: evidenceReferences }
      : {}),
  };
}

function normalizeConfidence(
  value: unknown,
): MeetingStructuredRelevanceConfidence | null {
  if (value !== "high" && value !== "medium" && value !== "low") {
    return null;
  }

  return value;
}

function normalizeEvidenceReferences(
  value: unknown,
): MeetingEvidenceReferenceV2[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(isEvidenceReferenceV2);
}

function isEvidenceReferenceV2(value: unknown): value is MeetingEvidenceReferenceV2 {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.evidence_id === "string" &&
    (value.document_id === null || typeof value.document_id === "string") &&
    (value.document_kind === "minutes" ||
      value.document_kind === "agenda" ||
      value.document_kind === "packet") &&
    typeof value.artifact_id === "string" &&
    typeof value.section_path === "string" &&
    (value.page_start === null || typeof value.page_start === "number") &&
    (value.page_end === null || typeof value.page_end === "number") &&
    (value.char_start === null || typeof value.char_start === "number") &&
    (value.char_end === null || typeof value.char_end === "number") &&
    (value.precision === "offset" ||
      value.precision === "span" ||
      value.precision === "section" ||
      value.precision === "file") &&
    (value.confidence === null ||
      value.confidence === "high" ||
      value.confidence === "medium" ||
      value.confidence === "low") &&
    typeof value.excerpt === "string"
  );
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null;
}