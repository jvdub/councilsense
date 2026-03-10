export type MeetingListItem = {
  id: string;
  city_id: string;
  city_name: string | null;
  meeting_uid: string;
  title: string;
  created_at: string;
  updated_at: string;
  meeting_date: string | null;
  body_name: string | null;
  status: string | null;
  confidence_label: string | null;
  reader_low_confidence: boolean;
};

export type CityMeetingsListResponse = {
  items: MeetingListItem[];
  next_cursor: string | null;
  limit: number;
};

export type MeetingEvidencePointer = {
  id: string;
  artifact_id: string;
  source_document_url: string | null;
  section_ref: string | null;
  char_start: number | null;
  char_end: number | null;
  excerpt: string;
};

export type MeetingClaim = {
  id: string;
  claim_order: number;
  claim_text: string;
  evidence: MeetingEvidencePointer[];
};

export type MeetingEvidenceReferenceV2 = {
  evidence_id: string;
  document_id: string | null;
  document_kind: "minutes" | "agenda" | "packet";
  artifact_id: string;
  section_path: string;
  page_start: number | null;
  page_end: number | null;
  char_start: number | null;
  char_end: number | null;
  precision: "offset" | "span" | "section" | "file";
  confidence: "high" | "medium" | "low" | null;
  excerpt: string;
};

export type MeetingStructuredRelevanceConfidence = "high" | "medium" | "low";

export type MeetingStructuredRelevanceField = {
  value: string;
  confidence?: MeetingStructuredRelevanceConfidence;
  evidence_references_v2?: MeetingEvidenceReferenceV2[];
};

export type MeetingStructuredRelevanceImpactTagName =
  | "housing"
  | "traffic"
  | "utilities"
  | "parks"
  | "fees"
  | "land_use";

export type MeetingStructuredRelevanceImpactTag = {
  tag: MeetingStructuredRelevanceImpactTagName;
  confidence?: MeetingStructuredRelevanceConfidence;
  evidence_references_v2?: MeetingEvidenceReferenceV2[];
};

export type MeetingStructuredRelevance = {
  subject?: MeetingStructuredRelevanceField;
  location?: MeetingStructuredRelevanceField;
  action?: MeetingStructuredRelevanceField;
  scale?: MeetingStructuredRelevanceField;
  impact_tags?: MeetingStructuredRelevanceImpactTag[];
};

export type MeetingSuggestedPromptId =
  | "project_identity"
  | "location"
  | "disposition"
  | "scale"
  | "timeline"
  | "next_step";

export type MeetingSuggestedPrompt = {
  prompt_id: MeetingSuggestedPromptId;
  prompt: string;
  answer: string;
  evidence_references_v2: MeetingEvidenceReferenceV2[];
};

export type MeetingPlannedItem = {
  planned_id: string;
  title: string;
  category: string;
  status: string;
  confidence: "high" | "medium" | "low";
  evidence_references_v2: MeetingEvidenceReferenceV2[];
  subject?: MeetingStructuredRelevanceField;
  location?: MeetingStructuredRelevanceField;
  action?: MeetingStructuredRelevanceField;
  scale?: MeetingStructuredRelevanceField;
  impact_tags?: MeetingStructuredRelevanceImpactTag[];
};

export type MeetingPlannedBlock = {
  generated_at: string;
  source_coverage: {
    minutes: "present" | "missing";
    agenda: "present" | "missing";
    packet: "present" | "missing";
  };
  items: MeetingPlannedItem[];
};

export type MeetingOutcomeItem = {
  outcome_id: string;
  title: string;
  result: string;
  confidence: "high" | "medium" | "low";
  evidence_references_v2: MeetingEvidenceReferenceV2[];
  subject?: MeetingStructuredRelevanceField;
  location?: MeetingStructuredRelevanceField;
  action?: MeetingStructuredRelevanceField;
  scale?: MeetingStructuredRelevanceField;
  impact_tags?: MeetingStructuredRelevanceImpactTag[];
};

export type MeetingOutcomesBlock = {
  generated_at: string;
  authority_source: "minutes";
  items: MeetingOutcomeItem[];
};

export type MeetingPlannedOutcomeMismatchItem = {
  mismatch_id: string;
  planned_id: string;
  outcome_id: string | null;
  severity: "high" | "medium" | "low";
  mismatch_type: string;
  description: string;
  reason_codes: string[];
  evidence_references_v2: MeetingEvidenceReferenceV2[];
};

export type MeetingPlannedOutcomeMismatchesBlock = {
  summary: {
    total: number;
    high: number;
    medium: number;
    low: number;
  };
  items: MeetingPlannedOutcomeMismatchItem[];
};

export type MeetingDetailResponse = {
  id: string;
  city_id: string;
  city_name: string | null;
  meeting_uid: string;
  title: string;
  created_at: string;
  updated_at: string;
  meeting_date: string | null;
  body_name: string | null;
  source_document_kind: string | null;
  source_document_url: string | null;
  source_meeting_url?: string | null;
  status: string | null;
  confidence_label: string | null;
  reader_low_confidence: boolean;
  publication_id: string | null;
  published_at: string | null;
  summary: string | null;
  key_decisions: string[];
  key_actions: string[];
  notable_topics: string[];
  claims: MeetingClaim[];
  evidence_references_v2?: MeetingEvidenceReferenceV2[];
  structured_relevance?: MeetingStructuredRelevance;
  suggested_prompts?: MeetingSuggestedPrompt[];
  planned?: MeetingPlannedBlock;
  outcomes?: MeetingOutcomesBlock;
  planned_outcome_mismatches?: MeetingPlannedOutcomeMismatchesBlock;
};

export type MeetingListFilters = {
  cursor?: string;
  limit?: number;
  status?: string;
};

export type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};
