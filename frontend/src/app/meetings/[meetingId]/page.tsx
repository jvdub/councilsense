import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../../lib/api/bootstrap";
import { fetchMeetingDetail } from "../../../lib/api/meetings";
import { getAuthTokenFromCookie } from "../../../lib/auth/session";
import { getMeetingDetailFeatureFlags, resolveMeetingDetailRenderState } from "../../../lib/meetings/detailRenderMode";
import { type MeetingOutcomeItem, type MeetingPlannedItem } from "../../../lib/models/meetings";
import { getOnboardingRedirectPath } from "../../../lib/onboarding/guard";
import { ConfidenceBanner } from "./ConfidenceBanner";
import { EvidenceReferences } from "./EvidenceReferences";
import { MismatchIndicators } from "./MismatchIndicators";

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

function renderValue(value: string | null | undefined, fallback: string) {
  const trimmedValue = value?.trim();

  return trimmedValue && trimmedValue.length > 0 ? trimmedValue : fallback;
}

function renderLabelValue(value: string | null | undefined, fallback: string) {
  const resolvedValue = renderValue(value, fallback);

  if (resolvedValue === fallback) {
    return fallback;
  }

  const normalizedValue = resolvedValue.replace(/[_-]+/g, " ");
  return normalizedValue.charAt(0).toUpperCase() + normalizedValue.slice(1);
}

function renderPlannedItems(items: MeetingPlannedItem[]) {
  if (items.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
        No planned items available.
      </p>
    );
  }

  return (
    <ul className="space-y-4">
      {items.map((item) => (
        <li key={item.planned_id} className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm">
          <p className="text-base font-semibold tracking-tight text-slate-950">
            {renderValue(item.title, "Untitled planned item")}
          </p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Category</dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.category, "Category unavailable")}
              </dd>
            </div>
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Status</dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.status, "Status unavailable")}
              </dd>
            </div>
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Confidence</dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.confidence, "Confidence unavailable")}
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

function renderOutcomeItems(items: MeetingOutcomeItem[]) {
  if (items.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
        No outcomes available.
      </p>
    );
  }

  return (
    <ul className="space-y-4">
      {items.map((item) => (
        <li key={item.outcome_id} className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm">
          <p className="text-base font-semibold tracking-tight text-slate-950">
            {renderValue(item.title, "Untitled outcome")}
          </p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Result</dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.result, "Result unavailable")}
              </dd>
            </div>
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Confidence</dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.confidence, "Confidence unavailable")}
              </dd>
            </div>
          </dl>
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

  const renderState = resolveMeetingDetailRenderState(
    detailResponse,
    getMeetingDetailFeatureFlags(),
  );
  const additivePlanned = renderState.mode === "additive" ? detailResponse.planned : undefined;
  const additiveOutcomes = renderState.mode === "additive" ? detailResponse.outcomes : undefined;

  return (
    <main
      className="mx-auto flex w-full max-w-5xl flex-col gap-6"
      data-render-mode={renderState.mode}
      data-render-fallback={renderState.modeFallbackReason ?? undefined}
      data-mismatch-signals={renderState.mismatchSignalsEnabled ? "enabled" : "disabled"}
      data-mismatch-fallback={renderState.mismatchFallbackReason ?? undefined}
    >
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

      {additivePlanned ? (
        <section aria-label="Planned" className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60">
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Planned</h2>
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,18rem)_1fr]">
            <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Generated</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {renderValue(additivePlanned.generated_at, "Unavailable")}
                </p>
              </div>
              <div className="mt-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Source coverage</h3>
                <dl className="mt-3 space-y-3 text-sm text-slate-700">
                  <div className="flex items-center justify-between gap-4 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                    <dt className="font-medium text-slate-800">Agenda</dt>
                    <dd>{renderLabelValue(additivePlanned.source_coverage.agenda, "Unavailable")}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-4 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                    <dt className="font-medium text-slate-800">Packet</dt>
                    <dd>{renderLabelValue(additivePlanned.source_coverage.packet, "Unavailable")}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-4 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                    <dt className="font-medium text-slate-800">Minutes</dt>
                    <dd>{renderLabelValue(additivePlanned.source_coverage.minutes, "Unavailable")}</dd>
                  </div>
                </dl>
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Agenda and packet items</h3>
              <div className="mt-4">{renderPlannedItems(additivePlanned.items)}</div>
            </div>
          </div>
        </section>
      ) : null}

      {additiveOutcomes ? (
        <section aria-label="Outcomes" className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60">
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">Outcomes</h2>
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,18rem)_1fr]">
            <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Generated</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {renderValue(additiveOutcomes.generated_at, "Unavailable")}
                </p>
              </div>
              <div className="mt-5 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Authority source</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {renderLabelValue(additiveOutcomes.authority_source, "Unavailable")}
                </p>
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Recorded outcomes</h3>
              <div className="mt-4">{renderOutcomeItems(additiveOutcomes.items)}</div>
            </div>
          </div>
        </section>
      ) : null}

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

      {renderState.mismatchSignalsEnabled && detailResponse.planned_outcome_mismatches ? (
        <MismatchIndicators mismatches={detailResponse.planned_outcome_mismatches} />
      ) : null}
    </main>
  );
}
