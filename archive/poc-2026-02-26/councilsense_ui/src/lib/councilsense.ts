export type MeetingListItem = {
  meeting_id: string;
  imported_at: string;
  meeting_date: string | null;
  meeting_location: string | null;
  title: string | null;
  source_pdf_path: string | null;
  source_text_path: string | null;
  badges?: {
    pass_a?: boolean;
    pass_b?: boolean;
    pass_c?: boolean;
  };
};

export type MeetingListResponse = {
  meetings: MeetingListItem[];
};

export type MeetingDetailResponse = {
  meeting: {
    meeting_id: string;
    imported_at: string;
    meeting_date: string | null;
    meeting_location: string | null;
    title: string | null;
    meeting_dir: string;
    source_pdf_path: string | null;
    source_text_path: string | null;
  };
  artifact_names: string[];
  artifacts: Record<string, unknown>;
  raw: Record<string, string>;
};

export async function apiGetJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Request failed (${res.status}): ${text}`);
  }
  return (await res.json()) as T;
}
