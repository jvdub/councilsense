import { cleanup, render, screen, within } from "@testing-library/react";
import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import type {
  MeetingClaim,
  MeetingDetailResponse,
  MeetingEvidenceReferenceV2,
  MeetingOutcomeItem,
  MeetingPlannedItem,
  MeetingPlannedOutcomeMismatchItem,
} from "../../../lib/models/meetings";
import {
  MEETING_DETAIL_MISMATCH_SIGNALS_FLAG,
  MEETING_DETAIL_PLANNED_OUTCOMES_FLAG,
} from "../../../lib/meetings/detailRenderMode";
import MeetingDetailPage from "./page";

const redirectMock = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`);
});

const getAuthTokenFromCookieMock = vi.fn();
const fetchBootstrapMock = vi.fn();
const getOnboardingRedirectPathMock = vi.fn();
const fetchMeetingDetailMock = vi.fn();
const originalPlannedOutcomesFlag =
  process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED;
const originalMismatchSignalsFlag =
  process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED;

const LATENCY_THRESHOLDS = {
  flagOffP95MaxMs: 35,
  flagOnP95MaxMs: 50,
  additiveDeltaMaxMs: 15,
} as const;

const LATENCY_WARMUP_COUNT = 5;
const LATENCY_SAMPLE_COUNT = 25;

vi.mock("next/navigation", () => ({
  redirect: (path: string) => redirectMock(path),
}));

vi.mock("../../../lib/auth/session", () => ({
  getAuthTokenFromCookie: () => getAuthTokenFromCookieMock(),
}));

vi.mock("../../../lib/api/bootstrap", () => ({
  fetchBootstrap: (authToken: string) => fetchBootstrapMock(authToken),
}));

vi.mock("../../../lib/onboarding/guard", () => ({
  getOnboardingRedirectPath: (bootstrap: unknown, currentPath: string) =>
    getOnboardingRedirectPathMock(bootstrap, currentPath),
}));

vi.mock("../../../lib/api/meetings", () => ({
  fetchMeetingDetail: (authToken: string, meetingId: string) =>
    fetchMeetingDetailMock(authToken, meetingId),
}));

function setFeatureFlags({
  plannedOutcomesEnabled,
  mismatchSignalsEnabled,
}: {
  plannedOutcomesEnabled: boolean;
  mismatchSignalsEnabled: boolean;
}) {
  process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = plannedOutcomesEnabled
    ? "true"
    : "false";
  process.env[MEETING_DETAIL_MISMATCH_SIGNALS_FLAG] = mismatchSignalsEnabled
    ? "true"
    : "false";
}

function buildEvidenceReference(
  id: string,
  overrides: Partial<MeetingEvidenceReferenceV2> = {},
): MeetingEvidenceReferenceV2 {
  return {
    evidence_id: id,
    document_id: `document-${id}`,
    document_kind: "minutes",
    artifact_id: `artifact-${id}`,
    section_path: `minutes.section.${id}`,
    page_start: 2,
    page_end: 2,
    char_start: 100,
    char_end: 180,
    precision: "span",
    confidence: "high",
    excerpt: `Evidence excerpt ${id}`,
    ...overrides,
  };
}

function buildClaim(index: number, evidenceCount = 3): MeetingClaim {
  return {
    id: `claim-${index}`,
    claim_order: index + 1,
    claim_text: `Claim ${index + 1}`,
    evidence: Array.from({ length: evidenceCount }, (_, evidenceIndex) => ({
      id: `pointer-${index + 1}-${evidenceIndex + 1}`,
      artifact_id: `artifact-${index + 1}-${evidenceIndex + 1}`,
      section_ref: `minutes.section.${index + 1}.${evidenceIndex + 1}`,
      char_start: 25 * (evidenceIndex + 1),
      char_end: 25 * (evidenceIndex + 1) + 40,
      excerpt: `Evidence pointer ${index + 1}.${evidenceIndex + 1}`,
    })),
  };
}

function buildPlannedItem(index: number): MeetingPlannedItem {
  return {
    planned_id: `planned-${index + 1}`,
    title: `Planned item ${index + 1}`,
    category: index % 2 === 0 ? "ordinance" : "briefing",
    status: "planned",
    confidence: index % 3 === 0 ? "high" : index % 3 === 1 ? "medium" : "low",
    evidence_references_v2: [buildEvidenceReference(`planned-${index + 1}`)],
  };
}

function buildOutcomeItem(index: number): MeetingOutcomeItem {
  return {
    outcome_id: `outcome-${index + 1}`,
    title: `Outcome item ${index + 1}`,
    result: index % 2 === 0 ? "approved" : "deferred",
    confidence: index % 3 === 0 ? "high" : index % 3 === 1 ? "medium" : "low",
    evidence_references_v2: [buildEvidenceReference(`outcome-${index + 1}`)],
  };
}

function buildMismatch(
  index: number,
  overrides: Partial<MeetingPlannedOutcomeMismatchItem> = {},
): MeetingPlannedOutcomeMismatchItem {
  return {
    mismatch_id: `mismatch-${index + 1}`,
    planned_id: `planned-${index + 1}`,
    outcome_id: `outcome-${index + 1}`,
    severity: index % 3 === 0 ? "high" : index % 3 === 1 ? "medium" : "low",
    mismatch_type: "disposition_change",
    description: `Mismatch ${index + 1}`,
    reason_codes: ["outcome_changed"],
    evidence_references_v2: [buildEvidenceReference(`mismatch-${index + 1}`)],
    ...overrides,
  };
}

function buildMeetingDetail(
  overrides: Partial<MeetingDetailResponse> = {},
): MeetingDetailResponse {
  return {
    id: "meeting-verification",
    city_id: "seattle-wa",
    meeting_uid: "uid-verification",
    title: "Council verification session",
    created_at: "2026-03-07T16:00:00Z",
    updated_at: "2026-03-07T16:05:00Z",
    status: "processed",
    confidence_label: "high",
    reader_low_confidence: false,
    publication_id: "publication-verification",
    published_at: "2026-03-07T16:10:00Z",
    summary: "Council completed the verification agenda.",
    key_decisions: ["Accepted the verification agenda"],
    key_actions: ["Staff to publish the verification packet"],
    notable_topics: ["Verification"],
    claims: [buildClaim(0)],
    planned: {
      generated_at: "2026-03-07T15:50:00Z",
      source_coverage: {
        minutes: "present",
        agenda: "present",
        packet: "present",
      },
      items: [buildPlannedItem(0)],
    },
    outcomes: {
      generated_at: "2026-03-07T16:02:00Z",
      authority_source: "minutes",
      items: [buildOutcomeItem(0)],
    },
    planned_outcome_mismatches: {
      summary: {
        total: 1,
        high: 1,
        medium: 0,
        low: 0,
      },
      items: [buildMismatch(0)],
    },
    ...overrides,
  };
}

function buildRepresentativeLatencyDetail(): MeetingDetailResponse {
  const claims = Array.from({ length: 24 }, (_, index) => buildClaim(index, 3));
  const plannedItems = Array.from({ length: 18 }, (_, index) =>
    buildPlannedItem(index),
  );
  const outcomeItems = Array.from({ length: 18 }, (_, index) =>
    buildOutcomeItem(index),
  );
  const mismatches = Array.from({ length: 12 }, (_, index) =>
    buildMismatch(index),
  );
  const mismatchSummary = mismatches.reduce(
    (summary, item) => {
      summary.total += 1;
      summary[item.severity] += 1;
      return summary;
    },
    { total: 0, high: 0, medium: 0, low: 0 },
  );

  return buildMeetingDetail({
    id: "meeting-latency-verification",
    meeting_uid: "uid-latency-verification",
    title: "Council latency verification session",
    summary:
      "Representative high-contention meeting detail payload for latency regression checks.",
    key_decisions: Array.from(
      { length: 12 },
      (_, index) => `Decision ${index + 1}`,
    ),
    key_actions: Array.from(
      { length: 12 },
      (_, index) => `Action ${index + 1}`,
    ),
    notable_topics: Array.from(
      { length: 8 },
      (_, index) => `Topic ${index + 1}`,
    ),
    claims,
    planned: {
      generated_at: "2026-03-07T15:50:00Z",
      source_coverage: {
        minutes: "present",
        agenda: "present",
        packet: "present",
      },
      items: plannedItems,
    },
    outcomes: {
      generated_at: "2026-03-07T16:02:00Z",
      authority_source: "minutes",
      items: outcomeItems,
    },
    planned_outcome_mismatches: {
      summary: mismatchSummary,
      items: mismatches,
    },
  });
}

function nearestRankPercentile(samples: number[], percentile: number): number {
  const sorted = [...samples].sort((left, right) => left - right);
  const rank = Math.max(1, Math.ceil((percentile / 100) * sorted.length));

  return sorted[rank - 1] ?? 0;
}

async function renderMeetingDetail(detail: MeetingDetailResponse) {
  fetchMeetingDetailMock.mockResolvedValueOnce(detail);

  return render(
    await MeetingDetailPage({
      params: Promise.resolve({ meetingId: detail.id }),
    }),
  );
}

async function measureRouteGenerationLatency(
  detail: MeetingDetailResponse,
  flags: { plannedOutcomesEnabled: boolean; mismatchSignalsEnabled: boolean },
) {
  setFeatureFlags(flags);
  fetchMeetingDetailMock.mockImplementation(async () => detail);

  for (
    let warmupIndex = 0;
    warmupIndex < LATENCY_WARMUP_COUNT;
    warmupIndex += 1
  ) {
    await MeetingDetailPage({
      params: Promise.resolve({ meetingId: detail.id }),
    });
  }

  const samples: number[] = [];

  for (
    let sampleIndex = 0;
    sampleIndex < LATENCY_SAMPLE_COUNT;
    sampleIndex += 1
  ) {
    const start = performance.now();

    await MeetingDetailPage({
      params: Promise.resolve({ meetingId: detail.id }),
    });

    samples.push(performance.now() - start);
  }

  return {
    p95Ms: nearestRankPercentile(samples, 95),
    samples,
  };
}

describe("MeetingDetailPage verification", () => {
  const returningBootstrap = {
    user_id: "user-returning",
    home_city_id: "seattle-wa",
    onboarding_required: false,
    supported_city_ids: ["seattle-wa", "portland-or"],
  };

  beforeEach(() => {
    redirectMock.mockClear();
    getAuthTokenFromCookieMock.mockReset();
    fetchBootstrapMock.mockReset();
    getOnboardingRedirectPathMock.mockReset();
    fetchMeetingDetailMock.mockReset();
    getAuthTokenFromCookieMock.mockResolvedValue("token-abc");
    fetchBootstrapMock.mockResolvedValue(returningBootstrap);
    getOnboardingRedirectPathMock.mockReturnValue(null);
    delete process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED;
    delete process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED;
  });

  it("keeps the baseline route accessible when additive sections are disabled", async () => {
    setFeatureFlags({
      plannedOutcomesEnabled: false,
      mismatchSignalsEnabled: false,
    });

    const { container } = await renderMeetingDetail(
      buildMeetingDetail({
        title: "Baseline accessibility session",
        summary: "Baseline accessibility summary.",
      }),
    );

    const sectionHeadings = screen.getAllByRole("heading", { level: 2 });
    const labelledRegions = Array.from(
      container.querySelectorAll("section[aria-label]"),
    ).map((section) => section.getAttribute("aria-label"));

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Baseline accessibility session",
      }),
    ).toBeInTheDocument();
    expect(sectionHeadings.map((heading) => heading.textContent)).toEqual([
      "Summary",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(labelledRegions).toEqual([
      "Summary",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(
      screen.getByRole("link", { name: "Back to meetings" }),
    ).toHaveAttribute("href", "/meetings");
    expect(
      screen.queryByRole("region", { name: "Planned" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Outcomes" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Mismatch indicators" }),
    ).not.toBeInTheDocument();
  });

  it("renders severity labels for evidence-backed mismatches and suppresses unsupported entries", async () => {
    setFeatureFlags({
      plannedOutcomesEnabled: true,
      mismatchSignalsEnabled: true,
    });

    const mismatches = [
      buildMismatch(0, {
        severity: "high",
        description: "High-severity mismatch backed by minutes.",
      }),
      buildMismatch(1, {
        severity: "medium",
        description: "Medium-severity mismatch backed by minutes.",
      }),
      buildMismatch(2, {
        severity: "low",
        description: "Low-severity mismatch backed by minutes.",
      }),
      buildMismatch(3, {
        severity: "high",
        description:
          "Unsupported mismatch without evidence should stay hidden.",
        evidence_references_v2: [],
      }),
    ];

    const { container } = await renderMeetingDetail(
      buildMeetingDetail({
        title: "Additive accessibility session",
        planned: {
          generated_at: "2026-03-07T15:50:00Z",
          source_coverage: {
            minutes: "present",
            agenda: "present",
            packet: "present",
          },
          items: [buildPlannedItem(0), buildPlannedItem(1)],
        },
        outcomes: {
          generated_at: "2026-03-07T16:02:00Z",
          authority_source: "minutes",
          items: [buildOutcomeItem(0), buildOutcomeItem(1)],
        },
        planned_outcome_mismatches: {
          summary: {
            total: mismatches.length,
            high: 2,
            medium: 1,
            low: 1,
          },
          items: mismatches,
        },
      }),
    );

    const labelledRegions = Array.from(
      container.querySelectorAll("section[aria-label]"),
    ).map((section) => section.getAttribute("aria-label"));
    const mismatchRegion = screen.getByRole("region", {
      name: "Mismatch indicators",
    });
    const mismatchItems = within(mismatchRegion).getAllByRole("listitem");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Additive accessibility session",
      }),
    ).toBeInTheDocument();
    expect(labelledRegions).toEqual([
      "Summary",
      "Planned",
      "Outcomes",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
      "Mismatch indicators",
    ]);
    expect(screen.getByRole("region", { name: "Planned" })).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Outcomes" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Mismatch indicators" }),
    ).toHaveAttribute("data-mismatch-indicator-state", "supported");
    expect(mismatchItems).toHaveLength(3);
    expect(
      within(mismatchRegion).getByText("High mismatch"),
    ).toBeInTheDocument();
    expect(
      within(mismatchRegion).getByText("Medium mismatch"),
    ).toBeInTheDocument();
    expect(
      within(mismatchRegion).getByText("Low mismatch"),
    ).toBeInTheDocument();
    expect(
      within(mismatchRegion).getByText(
        "High-severity mismatch backed by minutes.",
      ),
    ).toBeInTheDocument();
    expect(
      within(mismatchRegion).getByText(
        "Medium-severity mismatch backed by minutes.",
      ),
    ).toBeInTheDocument();
    expect(
      within(mismatchRegion).getByText(
        "Low-severity mismatch backed by minutes.",
      ),
    ).toBeInTheDocument();
    expect(
      within(mismatchRegion).queryByText(
        "Unsupported mismatch without evidence should stay hidden.",
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps meeting detail route generation within the agreed latency budget", async () => {
    const detail = buildRepresentativeLatencyDetail();
    const baseline = await measureRouteGenerationLatency(detail, {
      plannedOutcomesEnabled: false,
      mismatchSignalsEnabled: false,
    });
    const additive = await measureRouteGenerationLatency(detail, {
      plannedOutcomesEnabled: true,
      mismatchSignalsEnabled: true,
    });
    const additiveDelta = additive.p95Ms - baseline.p95Ms;

    expect(baseline.p95Ms).toBeLessThanOrEqual(
      LATENCY_THRESHOLDS.flagOffP95MaxMs,
    );
    expect(additive.p95Ms).toBeLessThanOrEqual(
      LATENCY_THRESHOLDS.flagOnP95MaxMs,
    );
    expect(additiveDelta).toBeLessThanOrEqual(
      LATENCY_THRESHOLDS.additiveDeltaMaxMs,
    );
  });
});

afterEach(() => {
  cleanup();
});

afterAll(() => {
  if (originalPlannedOutcomesFlag === undefined) {
    delete process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED;
  } else {
    process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED =
      originalPlannedOutcomesFlag;
  }

  if (originalMismatchSignalsFlag === undefined) {
    delete process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED;
  } else {
    process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED =
      originalMismatchSignalsFlag;
  }
});
