"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  MeetingsApiError,
  createMeetingProcessingRequest,
} from "../../lib/api/meetings";
import {
  buildMeetingDetailHref,
  canRequestMeetingSummary,
  getMeetingTileActionLabel,
  getMeetingTileBadgeLabel,
  getMeetingTileStatusCopy,
} from "../../lib/meetings/explorer";
import {
  formatCalendarDate,
  formatCityLabel,
  humanizeIdentifier,
} from "../../lib/meetings/presentation";
import { type MeetingListItem } from "../../lib/models/meetings";

type MeetingsExplorerProps = {
  authToken: string;
  cityId: string;
  initialItems: MeetingListItem[];
  returnToPath: string;
};

type TileFeedback = {
  kind: "success" | "error";
  message: string;
};

const activeBadgeClassNameByStatus = {
  discovered: "bg-amber-100 text-amber-900 border border-amber-200",
  queued: "bg-sky-100 text-sky-900 border border-sky-200",
  processing: "bg-cyan-100 text-cyan-900 border border-cyan-200",
  processed: "bg-emerald-100 text-emerald-900 border border-emerald-200",
  failed: "bg-rose-100 text-rose-900 border border-rose-200",
} as const;

const JOB_POLL_INTERVAL_MS = 5000;

export function MeetingsExplorer({
  authToken,
  cityId,
  initialItems,
  returnToPath,
}: MeetingsExplorerProps) {
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [feedbackById, setFeedbackById] = useState<
    Record<string, TileFeedback | undefined>
  >({});
  const hasPendingJobs = items.some(
    (item) =>
      item.processing.processing_status === "queued" ||
      item.processing.processing_status === "processing",
  );

  useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  useEffect(() => {
    if (!hasPendingJobs) {
      return;
    }

    const intervalId = window.setInterval(() => {
      if (
        typeof document !== "undefined" &&
        document.visibilityState === "hidden"
      ) {
        return;
      }
      router.refresh();
    }, JOB_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [hasPendingJobs, router]);

  async function handleRequestSummary(meeting: MeetingListItem) {
    if (!canRequestMeetingSummary(meeting) || !meeting.discovered_meeting) {
      return;
    }

    setSubmittingId(meeting.id);
    setFeedbackById((current) => ({
      ...current,
      [meeting.id]: undefined,
    }));

    try {
      const response = await createMeetingProcessingRequest(
        authToken,
        cityId,
        meeting.discovered_meeting.discovered_meeting_id,
      );
      const successMessage =
        response.processing.request_outcome === "already_active"
          ? "A summary request is already active for this meeting."
          : "We added this meeting to your summary requests.";

      setItems((current) =>
        current.map((item) => {
          if (item.id !== meeting.id) {
            return item;
          }

          return {
            ...item,
            meeting_id: response.meeting_id ?? item.meeting_id,
            processing: {
              ...item.processing,
              ...response.processing,
            },
          };
        }),
      );
      setFeedbackById((current) => ({
        ...current,
        [meeting.id]: {
          kind: "success",
          message: successMessage,
        },
      }));
    } catch (error) {
      let message = "Unable to request a summary right now.";

      if (error instanceof MeetingsApiError) {
        if (error.status === 429) {
          message =
            "You already have several summary requests in progress. Try again after one finishes.";
        } else if (error.status === 409) {
          message = "A briefing is already available for this meeting.";
        } else if (error.message) {
          message = error.message;
        }
      }

      setFeedbackById((current) => ({
        ...current,
        [meeting.id]: {
          kind: "error",
          message,
        },
      }));
    } finally {
      setSubmittingId(null);
    }
  }

  return (
    <ul className="grid gap-4 lg:grid-cols-2">
      {items.map((meeting) => {
        const detailHref = buildMeetingDetailHref(meeting, returnToPath);
        const actionLabel = getMeetingTileActionLabel(meeting);
        const requestable = canRequestMeetingSummary(meeting);
        const feedback = feedbackById[meeting.id];
        const status = meeting.processing.processing_status;

        return (
          <li
            key={meeting.id}
            className="group rounded-[1.75rem] border border-slate-200/80 bg-white/90 p-6 shadow-lg shadow-slate-200/60 transition hover:-translate-y-0.5 hover:shadow-xl"
          >
            <div className="flex h-full flex-col justify-between gap-5">
              <div className="space-y-3">
                <div
                  className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${activeBadgeClassNameByStatus[status]}`}
                >
                  {getMeetingTileBadgeLabel(meeting)}
                </div>
                <h2 className="text-xl font-semibold tracking-tight text-slate-950">
                  {detailHref ? (
                    <Link
                      href={detailHref}
                      className="transition hover:text-cyan-700"
                    >
                      {meeting.title}
                    </Link>
                  ) : (
                    <span>{meeting.title}</span>
                  )}
                </h2>
                <p className="text-sm font-medium leading-6 text-slate-700">
                  {formatCityLabel(meeting.city_name, meeting.city_id)}
                  {meeting.body_name && meeting.body_name !== meeting.title
                    ? ` • ${meeting.body_name}`
                    : ""}
                  {meeting.meeting_date
                    ? ` • ${formatCalendarDate(meeting.meeting_date)}`
                    : ""}
                </p>
                <p className="text-sm leading-6 text-slate-600">
                  {getMeetingTileStatusCopy(meeting)}
                </p>
                {meeting.processing.processing_status === "processed" ? (
                  <p className="text-sm leading-6 text-slate-600">
                    Publication status:{" "}
                    {humanizeIdentifier(meeting.status, "Processed")} ·
                    Confidence:{" "}
                    {humanizeIdentifier(meeting.confidence_label, "Unknown")}
                  </p>
                ) : (
                  <p className="text-sm leading-6 text-slate-600">
                    Source provider:{" "}
                    {humanizeIdentifier(
                      meeting.discovered_meeting?.source_provider_name,
                      "Catalog",
                    )}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-3 border-t border-slate-200 pt-4">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <time
                    className="text-sm text-slate-500"
                    dateTime={
                      meeting.processing.processing_status_updated_at ??
                      meeting.meeting_date ??
                      meeting.updated_at ??
                      undefined
                    }
                  >
                    {meeting.meeting_date
                      ? `Meeting date: ${formatCalendarDate(meeting.meeting_date)}`
                      : `Updated: ${formatCalendarDate(meeting.updated_at, "Unavailable")}`}
                  </time>
                  {detailHref && actionLabel ? (
                    <Link
                      href={detailHref}
                      className="text-sm font-semibold text-cyan-700 transition group-hover:text-cyan-900"
                    >
                      {actionLabel} →
                    </Link>
                  ) : null}
                  {requestable && actionLabel ? (
                    <button
                      type="button"
                      onClick={() => void handleRequestSummary(meeting)}
                      disabled={submittingId === meeting.id}
                      className="inline-flex items-center rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                    >
                      {submittingId === meeting.id
                        ? "Submitting…"
                        : actionLabel}
                    </button>
                  ) : null}
                </div>
                {feedback ? (
                  <p
                    role={feedback.kind === "error" ? "alert" : "status"}
                    aria-live="polite"
                    className={`rounded-2xl px-4 py-3 text-sm ${
                      feedback.kind === "error"
                        ? "border border-rose-200 bg-rose-50 text-rose-700"
                        : "border border-emerald-200 bg-emerald-50 text-emerald-700"
                    }`}
                  >
                    {feedback.message}
                  </p>
                ) : null}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
