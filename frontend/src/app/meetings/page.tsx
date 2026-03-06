import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../lib/api/bootstrap";
import { fetchCityMeetings } from "../../lib/api/meetings";
import { getAuthTokenFromCookie } from "../../lib/auth/session";
import { getOnboardingRedirectPath } from "../../lib/onboarding/guard";

const DEFAULT_LIMIT = 20;

type SearchParams = {
  cursor?: string | string[];
  prev?: string | string[];
  limit?: string | string[];
  meeting_id?: string | string[];
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

function buildMeetingsHref(cursor: string | null, prev: string | null, limit: number): string {
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

  const suffix = query.toString();
  return suffix ? `/meetings?${suffix}` : "/meetings";
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
  const meetingId = getSingleValue(resolvedParams.meeting_id)?.trim() ?? "";

  if (meetingId) {
    redirect(`/meetings/${encodeURIComponent(meetingId)}`);
  }

  const cursor = getSingleValue(resolvedParams.cursor);
  const prevCursor = getSingleValue(resolvedParams.prev);
  const limit = parseLimit(getSingleValue(resolvedParams.limit));

  let meetingsError: string | null = null;
  let listResponse: Awaited<ReturnType<typeof fetchCityMeetings>> | null = null;

  try {
    listResponse = await fetchCityMeetings(authToken, bootstrap.home_city_id, {
      cursor: cursor ?? undefined,
      limit,
    });
  } catch (error) {
    meetingsError = error instanceof Error ? error.message : "Failed to load meetings";
  }

  const hasMeetings = (listResponse?.items.length ?? 0) > 0;
  const nextCursor = listResponse?.next_cursor ?? null;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 lg:gap-8">
      <section className="rounded-[2rem] border border-slate-200/80 bg-slate-950 px-6 py-8 text-white shadow-2xl shadow-slate-400/20 sm:px-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-200">Civic briefings</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">Meetings</h1>
            <p className="mt-3 text-sm leading-7 text-slate-300 sm:text-base">
              Review recent local government meetings, scan confidence levels, and open a meeting for a concise, evidence-backed summary.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
              <span className="block text-xs uppercase tracking-[0.2em] text-slate-400">Home city</span>
              <span className="mt-1 block font-semibold text-white">{bootstrap.home_city_id}</span>
            </div>
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
        <p role="alert" className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 shadow-sm">
          Unable to load meetings. {meetingsError}
        </p>
      ) : null}

      {!meetingsError && !hasMeetings ? (
        <section className="rounded-3xl border border-dashed border-slate-300 bg-white/70 px-6 py-10 text-center shadow-sm">
          <p className="text-base font-medium text-slate-800">No meetings found for your city yet.</p>
          <p className="mt-2 text-sm text-slate-500">Check back after the next agenda packet or processing run.</p>
        </section>
      ) : null}

      {!meetingsError && hasMeetings ? (
        <ul className="grid gap-4 lg:grid-cols-2">
          {listResponse?.items.map((meeting) => (
            <li
              key={meeting.id}
              className="group rounded-[1.75rem] border border-slate-200/80 bg-white/90 p-6 shadow-lg shadow-slate-200/60 transition hover:-translate-y-0.5 hover:shadow-xl"
            >
              <div className="flex h-full flex-col justify-between gap-5">
                <div className="space-y-3">
                  <div className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-600">
                    {meeting.status ?? "unknown"}
                  </div>
                  <h2 className="text-xl font-semibold tracking-tight text-slate-950">
                    <Link href={`/meetings/${meeting.id}`} className="transition hover:text-cyan-700">
                      {meeting.title}
                    </Link>
                  </h2>
                  <p className="text-sm leading-6 text-slate-600">
                    Status: {meeting.status ?? "unknown"} · Confidence: {meeting.confidence_label ?? "unknown"}
                  </p>
                </div>

                <div className="flex items-center justify-between gap-4 border-t border-slate-200 pt-4">
                  <time className="text-sm text-slate-500" dateTime={meeting.created_at}>
                    Created: {meeting.created_at}
                  </time>
                  <Link
                    href={`/meetings/${meeting.id}`}
                    className="text-sm font-semibold text-cyan-700 transition group-hover:text-cyan-900"
                  >
                    View briefing →
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {!meetingsError && (prevCursor || cursor) ? (
        <div>
          <Link
            href={buildMeetingsHref(prevCursor, null, limit)}
            className="inline-flex items-center rounded-full border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
          >
            Load newer meetings
          </Link>
        </div>
      ) : null}

      {!meetingsError && nextCursor ? (
        <div>
          <Link
            href={buildMeetingsHref(nextCursor, cursor, limit)}
            className="inline-flex items-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Load older meetings
          </Link>
        </div>
      ) : null}
    </main>
  );
}
