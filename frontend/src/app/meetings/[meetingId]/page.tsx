import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { fetchBootstrap } from "../../../lib/api/bootstrap";
import { fetchMeetingDetail } from "../../../lib/api/meetings";
import { getAuthTokenFromCookie } from "../../../lib/auth/session";
import {
  getMeetingDetailFeatureFlags,
  resolveMeetingDetailRenderState,
} from "../../../lib/meetings/detailRenderMode";
import {
  getMeetingResidentScanFeatureFlags,
  resolveMeetingResidentScanRenderState,
  type MeetingResidentScanCardModel,
  type MeetingResidentScanFieldModel,
} from "../../../lib/meetings/residentScanMode";
import {
  formatCalendarDate,
  formatCityLabel,
  formatSourceKindLabel,
  formatTimestamp,
  humanizeIdentifier,
} from "../../../lib/meetings/presentation";
import {
  type MeetingOutcomeItem,
  type MeetingPlannedItem,
  type MeetingSuggestedPrompt,
} from "../../../lib/models/meetings";
import { getOnboardingRedirectPath } from "../../../lib/onboarding/guard";
import { ConfidenceBanner } from "./ConfidenceBanner";
import {
  EvidenceReferences,
  type ResidentScanEvidenceGroup,
  type SuggestedPromptEvidenceGroup,
} from "./EvidenceReferences";
import { MismatchIndicators } from "./MismatchIndicators";
import { SuggestedPrompts } from "./SuggestedPrompts";

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
        <li
          key={item}
          className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-700 shadow-sm"
        >
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
        <li
          key={item.planned_id}
          id={`planned-item-${item.planned_id}`}
          className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
        >
          <p className="text-base font-semibold tracking-tight text-slate-950">
            {renderValue(item.title, "Untitled planned item")}
          </p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Category
              </dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.category, "Category unavailable")}
              </dd>
            </div>
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Status
              </dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.status, "Status unavailable")}
              </dd>
            </div>
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Confidence
              </dt>
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
        <li
          key={item.outcome_id}
          id={`outcome-item-${item.outcome_id}`}
          className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
        >
          <p className="text-base font-semibold tracking-tight text-slate-950">
            {renderValue(item.title, "Untitled outcome")}
          </p>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Result
              </dt>
              <dd className="mt-2 text-sm text-slate-700">
                {renderLabelValue(item.result, "Result unavailable")}
              </dd>
            </div>
            <div className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
              <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Confidence
              </dt>
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

function renderResidentScanField(field: MeetingResidentScanFieldModel) {
  return (
    <div
      key={field.key}
      className="rounded-2xl border border-white bg-white px-4 py-3 shadow-sm"
    >
      <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
        {field.label}
      </dt>
      <dd className="mt-2 text-sm text-slate-700">
        {field.state === "present" ? field.value : "Not specified"}
      </dd>
    </div>
  );
}

function buildResidentScanEvidenceAnchorId(cardId: string) {
  return `resident-scan-evidence-${cardId.replace(/[^a-zA-Z0-9_-]+/g, "-")}`;
}

function buildSuggestedPromptEvidenceAnchorId(promptId: string) {
  return `suggested-prompt-evidence-${promptId.replace(/[^a-zA-Z0-9_-]+/g, "-")}`;
}

function getResidentScanSourceLabel(card: MeetingResidentScanCardModel) {
  if (card.source === "outcome") {
    return "Recorded outcome";
  }

  if (card.source === "planned") {
    return "Planned item";
  }

  return "Meeting overview";
}

function hasResidentScanEvidence(card: MeetingResidentScanCardModel) {
  return (
    Object.values(card.fields).some((field) => field.evidenceReferences.length > 0) ||
    card.impactTags.some((tag) => tag.evidenceReferences.length > 0)
  );
}

function buildResidentScanEvidenceGroups(
  cards: MeetingResidentScanCardModel[],
): ResidentScanEvidenceGroup[] {
  return cards
    .map((card) => {
      const entries: ResidentScanEvidenceGroup["entries"] = [
        ...Object.values(card.fields)
          .filter((field) => field.evidenceReferences.length > 0)
          .map((field) => ({
            label: field.label,
            references: field.evidenceReferences,
          })),
        ...card.impactTags
          .filter((tag) => tag.evidenceReferences.length > 0)
          .map((tag) => ({
            label: `Impact tag: ${humanizeIdentifier(tag.tag, tag.tag)}`,
            references: tag.evidenceReferences,
          })),
      ];

      if (entries.length === 0) {
        return null;
      }

      return {
        id: buildResidentScanEvidenceAnchorId(card.id),
        cardTitle: card.title,
        sourceLabel: getResidentScanSourceLabel(card),
        entries,
      };
    })
    .filter((group): group is ResidentScanEvidenceGroup => group !== null);
}

function buildSuggestedPromptEvidenceGroups(
  prompts: MeetingSuggestedPrompt[],
): SuggestedPromptEvidenceGroup[] {
  return prompts
    .filter((prompt) => prompt.evidence_references_v2.length > 0)
    .map((prompt) => ({
      id: buildSuggestedPromptEvidenceAnchorId(prompt.prompt_id),
      prompt: prompt.prompt,
      answer: prompt.answer,
      references: prompt.evidence_references_v2,
    }));
}

function getResidentScanSupportingDetailHref(
  card: MeetingResidentScanCardModel,
  options: {
    showPlannedSection: boolean;
    showOutcomesSection: boolean;
  },
) {
  if (card.source === "meeting") {
    return "#summary-section";
  }

  if (card.source === "planned" && options.showPlannedSection && card.sourceItemId) {
    return `#planned-item-${card.sourceItemId}`;
  }

  if (card.source === "outcome" && options.showOutcomesSection && card.sourceItemId) {
    return `#outcome-item-${card.sourceItemId}`;
  }

  return null;
}

function renderResidentScanCard(
  card: MeetingResidentScanCardModel,
  navigation: {
    supportingDetailHref: string | null;
    evidenceHref: string | null;
  },
) {
  const impactTags = card.impactTags;
  const hasNavigation =
    navigation.supportingDetailHref !== null || navigation.evidenceHref !== null;

  return (
    <li
      key={card.id}
      className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-base font-semibold tracking-tight text-slate-950">
            {card.title}
          </p>
          <p className="mt-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            {getResidentScanSourceLabel(card)}
          </p>
        </div>
        <span className="inline-flex w-fit rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-800">
          {card.state === "complete" ? "Complete" : "Partial"}
        </span>
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {renderResidentScanField(card.fields.subject)}
        {renderResidentScanField(card.fields.location)}
        {renderResidentScanField(card.fields.action)}
        {renderResidentScanField(card.fields.scale)}
      </dl>

      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Impact tags
        </p>
        {impactTags.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-2">
            {impactTags.map((tag) => (
              <li
                key={`${card.id}:${tag.tag}`}
                className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800"
              >
                {humanizeIdentifier(tag.tag, tag.tag)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-slate-600">
            No specific impact tags were identified for this scan.
          </p>
        )}
      </div>

      {card.state === "partial" ? (
        <p className="mt-4 text-sm text-slate-600">
          Some structured details were not available for this item.
        </p>
      ) : null}

      {hasNavigation ? (
        <div className="mt-4 flex flex-wrap gap-3">
          {navigation.supportingDetailHref ? (
            <a
              href={navigation.supportingDetailHref}
              className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-700 transition hover:border-slate-300 hover:bg-slate-100"
            >
              {card.source === "meeting" ? "View summary" : "View supporting detail"}
            </a>
          ) : null}
          {navigation.evidenceHref ? (
            <a
              href={navigation.evidenceHref}
              className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-800 transition hover:border-cyan-300 hover:bg-cyan-100"
            >
              View evidence
            </a>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-600">
          Supporting links are not available for this scan yet.
        </p>
      )}
    </li>
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
  let detailResponse: Awaited<ReturnType<typeof fetchMeetingDetail>> | null =
    null;

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
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">
            Meeting detail
          </h1>
          <p className="mt-4">
            <Link
              href="/meetings"
              className="text-sm font-semibold text-cyan-700 transition hover:text-cyan-900 hover:underline"
            >
              Back to meetings
            </Link>
          </p>
          <p
            role="alert"
            className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700"
          >
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
  const residentScanState = resolveMeetingResidentScanRenderState(
    detailResponse,
    getMeetingResidentScanFeatureFlags(),
  );
  const showPlannedSection =
    renderState.mode === "additive" &&
    renderState.contract.planned === "present";
  const showOutcomesSection =
    renderState.mode === "additive" &&
    renderState.contract.outcomes === "present";
  const showMismatchIndicators =
    renderState.mismatchSignalsEnabled &&
    renderState.contract.mismatches === "present";
  const additivePlanned = showPlannedSection
    ? (detailResponse.planned ?? null)
    : null;
  const additiveOutcomes = showOutcomesSection
    ? (detailResponse.outcomes ?? null)
    : null;
  const cityLabel = formatCityLabel(detailResponse.city_name, detailResponse.city_id);
  const meetingDateLabel = formatCalendarDate(
    detailResponse.meeting_date ?? detailResponse.created_at,
  );
  const bodyLabel = detailResponse.body_name?.trim() || detailResponse.title;
  const publishedLabel = formatTimestamp(detailResponse.published_at, "Pending");
  const showResidentScanCards =
    residentScanState.mode === "resident_scan" && residentScanState.cards.length > 0;
  const residentScanEvidenceGroups = buildResidentScanEvidenceGroups(
    residentScanState.cards,
  );
  const suggestedPrompts = detailResponse.suggested_prompts ?? [];
  const promptEvidenceGroups = buildSuggestedPromptEvidenceGroups(suggestedPrompts);
  const residentScanEvidenceHrefByCardId = new Map(
    residentScanState.cards
      .filter((card) => hasResidentScanEvidence(card))
      .map((card) => [card.id, `#${buildResidentScanEvidenceAnchorId(card.id)}`]),
  );
  const promptEvidenceHrefByPromptId = new Map(
    promptEvidenceGroups.map((group) => [
      group.id.replace(/^suggested-prompt-evidence-/, ""),
      `#${group.id}`,
    ]),
  );

  return (
    <main
      className="mx-auto flex w-full max-w-5xl flex-col gap-6"
      data-render-mode={renderState.mode}
      data-render-fallback={renderState.modeFallbackReason ?? undefined}
      data-resident-scan-mode={residentScanState.mode}
      data-resident-scan-fallback={
        residentScanState.modeFallbackReason ?? undefined
      }
      data-mismatch-signals={
        renderState.mismatchSignalsEnabled ? "enabled" : "disabled"
      }
      data-mismatch-fallback={renderState.mismatchFallbackReason ?? undefined}
    >
      <section className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-xl shadow-slate-200/60 backdrop-blur">
        <p>
          <Link
            href="/meetings"
            className="text-sm font-semibold text-cyan-700 transition hover:text-cyan-900 hover:underline"
          >
            Back to meetings
          </Link>
        </p>
        <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-700">
              {cityLabel}
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              {detailResponse.title}
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              {bodyLabel}
              {meetingDateLabel ? ` • ${meetingDateLabel}` : ""}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Status: {humanizeIdentifier(detailResponse.status, "Unknown")} · Confidence:{" "}
              {humanizeIdentifier(detailResponse.confidence_label, "Unknown")}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:w-104">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Meeting date</p>
              <p className="mt-2 font-medium text-slate-900">{meetingDateLabel}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Published</p>
              <p className="mt-2 font-medium text-slate-900">{publishedLabel}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 sm:col-span-2">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Source</p>
              {detailResponse.source_document_url ? (
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <span className="font-medium text-slate-900">
                    {formatSourceKindLabel(detailResponse.source_document_kind)}
                  </span>
                  <a
                    href={detailResponse.source_document_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-semibold text-cyan-700 transition hover:text-cyan-900 hover:underline"
                  >
                    Open source record
                  </a>
                </div>
              ) : (
                <p className="mt-2 font-medium text-slate-900">Source document unavailable</p>
              )}
            </div>
          </div>
        </div>
      </section>

      <ConfidenceBanner
        confidenceLabel={detailResponse.confidence_label}
        readerLowConfidence={detailResponse.reader_low_confidence}
      />

      {showResidentScanCards ? (
        <section
          aria-label="Resident impact scan"
          className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
        >
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
            Resident impact scan
          </h2>
          <p className="mt-4 text-sm leading-6 text-slate-600">
            Scan the structured highlights first, then use the full meeting detail below.
          </p>
          <ul className="mt-6 space-y-4">
            {residentScanState.cards.map((card) =>
              renderResidentScanCard(card, {
                supportingDetailHref: getResidentScanSupportingDetailHref(card, {
                  showPlannedSection,
                  showOutcomesSection,
                }),
                evidenceHref: residentScanEvidenceHrefByCardId.get(card.id) ?? null,
              }),
            )}
          </ul>
        </section>
      ) : null}

      <section
        id="summary-section"
        aria-label="Summary"
        className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
      >
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
          Summary
        </h2>
        <p className="mt-4 text-base leading-8 text-slate-700">
          {detailResponse.summary ?? "Summary is not available yet."}
        </p>
      </section>

      <SuggestedPrompts
        prompts={suggestedPrompts.map((prompt) => ({
          promptId: prompt.prompt_id,
          prompt: prompt.prompt,
          answer: prompt.answer,
          evidenceHref: promptEvidenceHrefByPromptId.get(prompt.prompt_id) ?? null,
          evidenceCount: prompt.evidence_references_v2.length,
        }))}
      />

      {additivePlanned ? (
        <section
          id="planned-section"
          aria-label="Planned"
          className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
        >
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
            Planned
          </h2>
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,18rem)_1fr]">
            <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Generated
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {renderValue(additivePlanned.generated_at, "Unavailable")}
                </p>
              </div>
              <div className="mt-5">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Source coverage
                </h3>
                <dl className="mt-3 space-y-3 text-sm text-slate-700">
                  <div className="flex items-center justify-between gap-4 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                    <dt className="font-medium text-slate-800">Agenda</dt>
                    <dd>
                      {renderLabelValue(
                        additivePlanned.source_coverage.agenda,
                        "Unavailable",
                      )}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between gap-4 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                    <dt className="font-medium text-slate-800">Packet</dt>
                    <dd>
                      {renderLabelValue(
                        additivePlanned.source_coverage.packet,
                        "Unavailable",
                      )}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between gap-4 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                    <dt className="font-medium text-slate-800">Minutes</dt>
                    <dd>
                      {renderLabelValue(
                        additivePlanned.source_coverage.minutes,
                        "Unavailable",
                      )}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                Agenda and packet items
              </h3>
              <div className="mt-4">
                {renderPlannedItems(additivePlanned.items)}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {additiveOutcomes ? (
        <section
          id="outcomes-section"
          aria-label="Outcomes"
          className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
        >
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
            Outcomes
          </h2>
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,18rem)_1fr]">
            <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Generated
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {renderValue(additiveOutcomes.generated_at, "Unavailable")}
                </p>
              </div>
              <div className="mt-5 rounded-2xl border border-white bg-white px-4 py-3 shadow-sm">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Authority source
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {renderLabelValue(
                    additiveOutcomes.authority_source,
                    "Unavailable",
                  )}
                </p>
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
                Recorded outcomes
              </h3>
              <div className="mt-4">
                {renderOutcomeItems(additiveOutcomes.items)}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      <section
        aria-label="Decisions and actions"
        className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
      >
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
          Decisions and actions
        </h2>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
              Key decisions
            </h3>
            {renderStringList(
              detailResponse.key_decisions,
              "No key decisions available.",
            )}
          </div>
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
              Key actions
            </h3>
            {renderStringList(
              detailResponse.key_actions,
              "No key actions available.",
            )}
          </div>
        </div>
      </section>

      <section
        aria-label="Notable topics"
        className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
      >
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
          Notable topics
        </h2>
        {renderStringList(
          detailResponse.notable_topics,
          "No notable topics available.",
        )}
      </section>

      <section
        id="evidence-references-section"
        aria-label="Evidence references"
        className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
      >
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
          Evidence references
        </h2>
        <div className="mt-6">
          <EvidenceReferences
            claims={detailResponse.claims}
            evidenceReferencesV2={detailResponse.evidence_references_v2 ?? []}
            residentScanEvidenceGroups={residentScanEvidenceGroups}
            promptEvidenceGroups={promptEvidenceGroups}
            sourceDocumentKind={detailResponse.source_document_kind}
            sourceDocumentUrl={detailResponse.source_document_url}
          />
        </div>
      </section>

      {showMismatchIndicators && detailResponse.planned_outcome_mismatches ? (
        <MismatchIndicators
          mismatches={detailResponse.planned_outcome_mismatches}
        />
      ) : null}
    </main>
  );
}
