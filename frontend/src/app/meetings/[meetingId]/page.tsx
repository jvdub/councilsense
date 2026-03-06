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
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
        {emptyMessage}
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item} className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-700 shadow-sm">
          {item}
        </li>
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
  const redirectPath = getOnboardingRedirectPath(bootstrap, "/meetings");

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
      <main className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <section className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-xl shadow-slate-200/60 backdrop-blur">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Meeting detail</h1>
          <p className="mt-4">
            <Link href="/meetings" className="text-sm font-semibold text-cyan-700 transition hover:text-cyan-900 hover:underline">
              Back to meetings
            </Link>
          </p>
          <p role="alert" className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
            Unable to load meeting detail. {detailError ?? "Unknown error"}
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <section className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-xl shadow-slate-200/60 backdrop-blur">
        <p>
          <Link href="/meetings" className="text-sm font-semibold text-cyan-700 transition hover:text-cyan-900 hover:underline">
            Back to meetings
          </Link>
        </p>
        <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{detailResponse.title}</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Status: {detailResponse.status ?? "unknown"} · Confidence: {detailResponse.confidence_label ?? "unknown"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <p>
              <span className="font-medium text-slate-800">Published:</span>{" "}
              {detailResponse.published_at ?? "Pending"}
            </p>
          </div>
        </div>
      </section>

      <ConfidenceBanner
        confidenceLabel={detailResponse.confidence_label}
        readerLowConfidence={detailResponse.reader_low_confidence}
      />

      <section aria-label="Summary" className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Summary</h2>
        <p className="mt-4 text-base leading-8 text-slate-700">{detailResponse.summary ?? "Summary is not available yet."}</p>
      </section>

      <section aria-label="Decisions and actions" className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Decisions and actions</h2>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Key decisions</h3>
        {renderStringList(
          detailResponse.key_decisions,
          "No key decisions available.",
        )}
          </div>
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Key actions</h3>
            {renderStringList(detailResponse.key_actions, "No key actions available.")}
          </div>
        </div>
      </section>

      <section aria-label="Notable topics" className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Notable topics</h2>
        {renderStringList(detailResponse.notable_topics, "No notable topics available.")}
      </section>

      <section aria-label="Evidence references" className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Evidence references</h2>
        <div className="mt-6">
        <EvidenceReferences claims={detailResponse.claims} />
        </div>
      </section>
    </main>
  );
}
