export type MeetingListItem = {
  id: string;
  city_id: string;
  meeting_uid: string;
  title: string;
  created_at: string;
  updated_at: string;
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

export type MeetingDetailResponse = {
  id: string;
  city_id: string;
  meeting_uid: string;
  title: string;
  created_at: string;
  updated_at: string;
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
