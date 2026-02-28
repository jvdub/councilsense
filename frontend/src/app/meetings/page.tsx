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

export default async function MeetingsPage({ searchParams }: MeetingsPageProps = {}) {
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
    <main>
      <h1>Meetings</h1>
      {meetingsError ? <p role="alert">Unable to load meetings. {meetingsError}</p> : null}

      {!meetingsError && !hasMeetings ? <p>No meetings found for your city yet.</p> : null}

      {!meetingsError && hasMeetings ? (
        <ul>
          {listResponse?.items.map((meeting) => (
            <li key={meeting.id}>
              <h2>{meeting.title}</h2>
              <p>
                Status: {meeting.status ?? "unknown"} · Confidence: {meeting.confidence_label ?? "unknown"}
              </p>
              <time dateTime={meeting.created_at}>Created: {meeting.created_at}</time>
            </li>
          ))}
        </ul>
      ) : null}

      {!meetingsError && (prevCursor || cursor) ? (
        <p>
          <Link href={buildMeetingsHref(prevCursor, null, limit)}>Load newer meetings</Link>
        </p>
      ) : null}

      {!meetingsError && nextCursor ? (
        <p>
          <Link href={buildMeetingsHref(nextCursor, cursor, limit)}>Load older meetings</Link>
        </p>
      ) : null}
    </main>
  );
}
