import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../../lib/api/bootstrap";
import { fetchMeetingDetail } from "../../../lib/api/meetings";
import { getAuthTokenFromCookie } from "../../../lib/auth/session";
import { getOnboardingRedirectPath } from "../../../lib/onboarding/guard";
import { ConfidenceBanner } from "./ConfidenceBanner";
import { EvidenceReferences } from "./EvidenceReferences";

type MeetingDetailPageProps = {
  params: Promise<{ meetingId: string }>;
};

function renderStringList(items: string[], emptyMessage: string) {
  if (items.length === 0) {
    return <p>{emptyMessage}</p>;
  }

  return (
    <ul>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export default async function MeetingDetailPage({
  params,
}: MeetingDetailPageProps) {
  const authToken = await getAuthTokenFromCookie();

  if (!authToken) {
    redirect("/auth/sign-in");
  }

  const { meetingId } = await params;
  const bootstrap = await fetchBootstrap(authToken);
  const redirectPath = getOnboardingRedirectPath(
    bootstrap,
    `/meetings/${meetingId}`,
  );

  if (redirectPath) {
    redirect(redirectPath);
  }

  if (!bootstrap.home_city_id) {
    redirect("/onboarding/city");
  }

  let detailError: string | null = null;
  let detailResponse: Awaited<ReturnType<typeof fetchMeetingDetail>> | null = null;

  try {
    detailResponse = await fetchMeetingDetail(authToken, meetingId);
  } catch (error) {
    detailError =
      error instanceof Error ? error.message : "Failed to load meeting detail";
  }

  if (detailError || !detailResponse) {
    return (
      <main>
        <h1>Meeting detail</h1>
        <p>
          <Link href="/meetings">Back to meetings</Link>
        </p>
        <p role="alert">Unable to load meeting detail. {detailError ?? "Unknown error"}</p>
      </main>
    );
  }

  return (
    <main>
      <p>
        <Link href="/meetings">Back to meetings</Link>
      </p>
      <h1>{detailResponse.title}</h1>
      <p>
        Status: {detailResponse.status ?? "unknown"} · Confidence:{" "}
        {detailResponse.confidence_label ?? "unknown"}
      </p>
      <ConfidenceBanner
        confidenceLabel={detailResponse.confidence_label}
        readerLowConfidence={detailResponse.reader_low_confidence}
      />

      <section aria-label="Summary">
        <h2>Summary</h2>
        <p>{detailResponse.summary ?? "Summary is not available yet."}</p>
      </section>

      <section aria-label="Decisions and actions">
        <h2>Decisions and actions</h2>
        <h3>Key decisions</h3>
        {renderStringList(
          detailResponse.key_decisions,
          "No key decisions available.",
        )}
        <h3>Key actions</h3>
        {renderStringList(detailResponse.key_actions, "No key actions available.")}
      </section>

      <section aria-label="Notable topics">
        <h2>Notable topics</h2>
        {renderStringList(detailResponse.notable_topics, "No notable topics available.")}
      </section>

      <section aria-label="Evidence references">
        <h2>Evidence references</h2>
        <EvidenceReferences claims={detailResponse.claims} />
      </section>
    </main>
  );
}
