import { type MeetingListItem } from "../models/meetings";

export const MEETING_EXPLORER_FLAG =
  "NEXT_PUBLIC_ST039_UI_MEETING_EXPLORER_ENABLED";

export function isMeetingExplorerEnabled(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return env[MEETING_EXPLORER_FLAG] !== "false";
}

export function canRequestMeetingSummary(meeting: MeetingListItem): boolean {
  const normalizedMeetingDate = meeting.meeting_date?.trim();
  const isFutureMeeting =
    !!normalizedMeetingDate &&
    /^\d{4}-\d{2}-\d{2}$/.test(normalizedMeetingDate) &&
    normalizedMeetingDate > new Date().toISOString().slice(0, 10);

  return (
    !isFutureMeeting &&
    meeting.discovered_meeting !== null &&
    (meeting.processing.processing_status === "discovered" ||
      meeting.processing.processing_status === "failed")
  );
}

export function buildMeetingDetailHref(
  meeting: MeetingListItem,
  returnToPath: string,
): string | null {
  if (meeting.processing.processing_status !== "processed") {
    return null;
  }
  if (!meeting.detail_available) {
    return null;
  }

  const targetMeetingId = meeting.meeting_id ?? meeting.id;
  const query = new URLSearchParams();

  if (returnToPath && returnToPath !== "/meetings") {
    query.set("returnTo", returnToPath);
  }

  const suffix = query.toString();
  return suffix
    ? `/meetings/${encodeURIComponent(targetMeetingId)}?${suffix}`
    : `/meetings/${encodeURIComponent(targetMeetingId)}`;
}

export function getMeetingTileBadgeLabel(meeting: MeetingListItem): string {
  switch (meeting.processing.processing_status) {
    case "discovered":
      return "Ready to request";
    case "queued":
      return "Queued";
    case "processing":
      return "Processing";
    case "processed":
      return "Briefing ready";
    case "failed":
      return "Needs retry";
    default:
      return "Meeting";
  }
}

export function getMeetingTileStatusCopy(meeting: MeetingListItem): string {
  switch (meeting.processing.processing_status) {
    case "discovered":
      return "This meeting is available from the source catalog and ready for a summary request.";
    case "queued":
      return "A summary request is already active for this meeting.";
    case "processing":
      return "We are assembling the briefing for this meeting now.";
    case "processed":
      return "A briefing is ready to open for this meeting.";
    case "failed":
      return "A previous summary attempt did not finish. You can request a fresh attempt.";
    default:
      return "Meeting state unavailable.";
  }
}

export function getMeetingTileActionLabel(meeting: MeetingListItem): string | null {
  if (meeting.processing.processing_status === "discovered") {
    return "Request summary";
  }
  if (meeting.processing.processing_status === "failed") {
    return "Try again";
  }
  if (meeting.processing.processing_status === "processed") {
    return "View briefing";
  }
  return null;
}

export function resolveMeetingReturnPath(value: string | string[] | undefined): string {
  const rawValue = Array.isArray(value) ? value[0] : value;
  const normalized = rawValue?.trim();

  if (!normalized || !normalized.startsWith("/meetings")) {
    return "/meetings";
  }

  return normalized;
}