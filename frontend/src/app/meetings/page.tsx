import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../lib/api/bootstrap";
import { fetchCityMeetings } from "../../lib/api/meetings";
import { getAuthTokenFromCookie } from "../../lib/auth/session";
import { isMeetingExplorerEnabled } from "../../lib/meetings/explorer";
import { formatCityLabel } from "../../lib/meetings/presentation";
import { getOnboardingRedirectPath } from "../../lib/onboarding/guard";
import { MeetingsExplorer } from "./MeetingsExplorer";

const DEFAULT_LIMIT = 20;

type SearchParams = {
  cursor?: string | string[];
  prev?: string | string[];
  limit?: string | string[];
  meeting_id?: string | string[];
  show_future?: string | string[];
};

type MeetingsPageProps = {
  searchParams?: Promise<SearchParams>;
};

function getSingleValue(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }

  return value ?? null;
}

function parseLimit(rawLimit: string | null): number {
  if (!rawLimit) {
    return DEFAULT_LIMIT;
  }

  const parsed = Number.parseInt(rawLimit, 10);

  if (!Number.isFinite(parsed) || parsed < 1) {
    return DEFAULT_LIMIT;
  }

  return Math.min(parsed, 100);
}

function buildMeetingsHref(
  cursor: string | null,
  prev: string | null,
  limit: number,
  showFuture: boolean,
): string {
  const query = new URLSearchParams();

  if (cursor) {
    query.set("cursor", cursor);
  }
  if (prev) {
    query.set("prev", prev);
  }
  if (limit !== DEFAULT_LIMIT) {
    query.set("limit", String(limit));
  }
  if (showFuture) {
    query.set("show_future", "true");
  }

  const suffix = query.toString();
  return suffix ? `/meetings?${suffix}` : "/meetings";
}

function isFutureMeetingsEnabled(value: string | null): boolean {
  return value === "true";
}

function getTodayDateKey(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

function isFutureMeetingDate(
  meetingDate: string | null | undefined,
  todayDateKey: string,
): boolean {
  const normalized = meetingDate?.trim();

  if (!normalized || !/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    return false;
  }

  return normalized > todayDateKey;
}

function getBaselineExplorerItems(
  items: Awaited<ReturnType<typeof fetchCityMeetings>>["items"],
) {
  return isMeetingExplorerEnabled()
    ? items
    : items.filter(
        (meeting) => meeting.processing.processing_status === "processed",
      );
}

function hasFutureMeetingsInItems(
  items: Awaited<ReturnType<typeof fetchCityMeetings>>["items"],
): boolean {
  const todayDateKey = getTodayDateKey();
  return getBaselineExplorerItems(items).some((meeting) =>
    isFutureMeetingDate(meeting.meeting_date, todayDateKey),
  );
}

function getExplorerItems(
  items: Awaited<ReturnType<typeof fetchCityMeetings>>["items"],
  showFutureMeetings: boolean,
) {
  const baselineItems = getBaselineExplorerItems(items);

  if (showFutureMeetings) {
    return baselineItems;
  }

  const todayDateKey = getTodayDateKey();
  return baselineItems.filter(
    (meeting) => !isFutureMeetingDate(meeting.meeting_date, todayDateKey),
  );
}

async function fetchMeetingsForExplorer(
  authToken: string,
  cityId: string,
  {
    cursor,
    limit,
    showFutureMeetings,
  }: {
    cursor?: string;
    limit: number;
    showFutureMeetings: boolean;
  },
): Promise<{
  response: Awaited<ReturnType<typeof fetchCityMeetings>>;
  hasFutureMeetings: boolean;
}> {
  if (showFutureMeetings && isMeetingExplorerEnabled()) {
    const response = await fetchCityMeetings(authToken, cityId, {
      cursor,
      limit,
    });

    return {
      response,
      hasFutureMeetings: hasFutureMeetingsInItems(response.items),
    };
  }

  let currentCursor = cursor;
  let nextCursor: string | null = null;
  let backfillActive = false;
  let hasFutureMeetings = false;
  const visibleItems: Awaited<ReturnType<typeof fetchCityMeetings>>["items"] =
    [];

  while (true) {
    const response = await fetchCityMeetings(authToken, cityId, {
      cursor: currentCursor,
      limit,
    });
    const pageItems = getExplorerItems(response.items, showFutureMeetings);
    backfillActive ||= pageItems.length < response.items.length;
    hasFutureMeetings ||= hasFutureMeetingsInItems(response.items);
    const remainingSlots = limit - visibleItems.length;

    if (remainingSlots > 0) {
      visibleItems.push(...pageItems.slice(0, remainingSlots));
    }

    nextCursor = response.next_cursor;

    if (
      !backfillActive ||
      visibleItems.length >= limit ||
      response.next_cursor === null
    ) {
      return {
        response: {
          ...response,
          items: visibleItems,
          next_cursor: nextCursor,
        },
        hasFutureMeetings,
      };
    }

    if (response.next_cursor === currentCursor) {
      return {
        response: {
          ...response,
          items: visibleItems,
          next_cursor: response.next_cursor,
        },
        hasFutureMeetings,
      };
    }

    currentCursor = response.next_cursor;
  }
}

export default async function MeetingsPage(props: MeetingsPageProps) {
  const { searchParams } = props ?? {};
  const authToken = await getAuthTokenFromCookie();

  if (!authToken) {
    redirect("/auth/sign-in");
  }

  const bootstrap = await fetchBootstrap(authToken);
  const redirectPath = getOnboardingRedirectPath(bootstrap, "/meetings");

  if (redirectPath) {
    redirect(redirectPath);
  }

  if (!bootstrap.home_city_id) {
    redirect("/onboarding/city");
  }

  const resolvedParams = (await searchParams) ?? {};
  const cursor = getSingleValue(resolvedParams.cursor);
  const prevCursor = getSingleValue(resolvedParams.prev);
  const limit = parseLimit(getSingleValue(resolvedParams.limit));
  const showFutureMeetings = isFutureMeetingsEnabled(
    getSingleValue(resolvedParams.show_future),
  );
  const meetingId = getSingleValue(resolvedParams.meeting_id)?.trim() ?? "";
  const currentListHref = buildMeetingsHref(
    cursor,
    prevCursor,
    limit,
    showFutureMeetings,
  );

  if (meetingId) {
    const query = new URLSearchParams({ returnTo: currentListHref });
    redirect(`/meetings/${encodeURIComponent(meetingId)}?${query.toString()}`);
  }

  let meetingsError: string | null = null;
  let listResponse: Awaited<ReturnType<typeof fetchCityMeetings>> | null = null;
  let hasFutureMeetings = false;

  try {
    const explorerResponse = await fetchMeetingsForExplorer(
      authToken,
      bootstrap.home_city_id,
      {
        cursor: cursor ?? undefined,
        limit,
        showFutureMeetings,
      },
    );
    listResponse = explorerResponse.response;
    hasFutureMeetings = explorerResponse.hasFutureMeetings;
  } catch (error) {
    meetingsError =
      error instanceof Error ? error.message : "Failed to load meetings";
  }

  const explorerItems = listResponse?.items ?? [];
  const hasMeetings = explorerItems.length > 0;
  const nextCursor = listResponse?.next_cursor ?? null;
  const homeCityLabel = formatCityLabel(
    explorerItems[0]?.city_name ?? null,
    bootstrap.home_city_id,
  );

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 lg:gap-8">
      <section className="rounded-[2rem] border border-slate-200/80 bg-slate-950 px-6 py-8 text-white shadow-2xl shadow-slate-400/20 sm:px-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-200">
              Civic briefings
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">
              Meetings
            </h1>
            <p className="mt-3 text-sm leading-7 text-slate-300 sm:text-base">
              Browse source meetings for your city, request a briefing when one
              is missing, and open finished summaries without losing your place
              in the explorer.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
              <span className="block text-xs uppercase tracking-[0.2em] text-slate-400">
                Home city
              </span>
              <span className="mt-1 block font-semibold text-white">
                {homeCityLabel}
              </span>
            </div>
            {hasFutureMeetings || showFutureMeetings ? (
              <Link
                href={buildMeetingsHref(
                  cursor,
                  prevCursor,
                  limit,
                  !showFutureMeetings,
                )}
                className="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                {showFutureMeetings
                  ? "Hide upcoming meetings"
                  : "Show upcoming meetings"}
              </Link>
            ) : (
              <span className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-300">
                No future meetings with published agendas yet
              </span>
            )}
            <Link
              href="/settings"
              className="inline-flex items-center justify-center rounded-full border border-cyan-300/30 bg-cyan-400/10 px-5 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20"
            >
              Manage alerts
            </Link>
          </div>
        </div>
      </section>

      {meetingsError ? (
        <p
          role="alert"
          className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 shadow-sm"
        >
          Unable to load meetings. {meetingsError}
        </p>
      ) : null}

      {!meetingsError && !hasMeetings ? (
        <section className="rounded-3xl border border-dashed border-slate-300 bg-white/70 px-6 py-10 text-center shadow-sm">
          <p className="text-base font-medium text-slate-800">
            {isMeetingExplorerEnabled()
              ? showFutureMeetings
                ? "No meetings found for your city yet."
                : "No past or current meetings found for your city yet."
              : "No processed meetings found for your city yet."}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            {isMeetingExplorerEnabled()
              ? showFutureMeetings
                ? "Check back after the next agenda packet, source sync, or processing run."
                : "Upcoming meetings are hidden by default. Show upcoming meetings to browse future sessions."
              : "Turn the explorer back on after rollout, or check back after the next processing run."}
          </p>
        </section>
      ) : null}

      {!meetingsError && hasMeetings ? (
        <MeetingsExplorer
          authToken={authToken}
          cityId={bootstrap.home_city_id}
          initialItems={explorerItems}
          returnToPath={currentListHref}
        />
      ) : null}

      {!meetingsError && (prevCursor || cursor) ? (
        <div>
          <Link
            href={buildMeetingsHref(
              prevCursor,
              null,
              limit,
              showFutureMeetings,
            )}
            className="inline-flex items-center rounded-full border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
          >
            Load newer meetings
          </Link>
        </div>
      ) : null}

      {!meetingsError && nextCursor ? (
        <div>
          <Link
            href={buildMeetingsHref(
              nextCursor,
              cursor,
              limit,
              showFutureMeetings,
            )}
            className="inline-flex items-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Load older meetings
          </Link>
        </div>
      ) : null}
    </main>
  );
}
