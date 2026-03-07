import { cleanup, render, screen, within } from "@testing-library/react";
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MeetingDetailPage from "./page";
import {
  MEETING_DETAIL_MISMATCH_SIGNALS_FLAG,
  MEETING_DETAIL_PLANNED_OUTCOMES_FLAG,
} from "../../../lib/meetings/detailRenderMode";

const redirectMock = vi.fn((path: string) => {
  throw new Error(`REDIRECT:${path}`);
});

const getAuthTokenFromCookieMock = vi.fn();
const fetchBootstrapMock = vi.fn();
const getOnboardingRedirectPathMock = vi.fn();
const fetchMeetingDetailMock = vi.fn();
const originalPlannedOutcomesFlag = process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED;
const originalMismatchSignalsFlag = process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED;

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

describe("MeetingDetailPage", () => {
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

  it("redirects unauthenticated users to sign-in", async () => {
    getAuthTokenFromCookieMock.mockResolvedValueOnce(null);

    await expect(
      MeetingDetailPage({ params: Promise.resolve({ meetingId: "meeting-1" }) }),
    ).rejects.toThrow("REDIRECT:/auth/sign-in");
    expect(fetchBootstrapMock).not.toHaveBeenCalled();
  });

  it("renders summary, decisions, topics, and evidence references", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-1",
      city_id: "seattle-wa",
      meeting_uid: "uid-1",
      title: "Council Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-1",
      published_at: "2026-02-25 19:00:00",
      summary: "Council approved the downtown transit plan.",
      key_decisions: ["Approved downtown transit plan"],
      key_actions: ["Staff to publish implementation timeline"],
      notable_topics: ["Transit", "Budget"],
      claims: [
        {
          id: "claim-1",
          claim_order: 1,
          claim_text: "Council approved the transit plan.",
          evidence: [
            {
              id: "pointer-1",
              artifact_id: "artifact-1",
              section_ref: "minutes.section.4",
              char_start: 12,
              char_end: 80,
              excerpt: "Council voted 6-1 to approve the transit plan.",
            },
          ],
        },
      ],
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-1" }),
      }),
    );

    const main = container.querySelector("main[data-render-mode]");

    expect(screen.getByRole("heading", { name: "Council Session" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Summary" })).toBeInTheDocument();
    expect(screen.getByText("Council approved the downtown transit plan.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decisions and actions" })).toBeInTheDocument();
    expect(screen.getByText("Approved downtown transit plan")).toBeInTheDocument();
    expect(screen.getByText("Staff to publish implementation timeline")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Notable topics" })).toBeInTheDocument();
    expect(screen.getByText("Transit")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evidence references" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Planned" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Outcomes" })).not.toBeInTheDocument();
    expect(screen.getByText("Council approved the transit plan.")).toBeInTheDocument();
    expect(screen.getByText("Council voted 6-1 to approve the transit plan.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "minutes.section.4" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to meetings" })).toHaveAttribute(
      "href",
      "/meetings",
    );
    expect(main).toHaveAttribute("data-render-mode", "baseline");
    expect(main).toHaveAttribute("data-render-fallback", "planned_outcomes_flag_disabled");
    expect(fetchMeetingDetailMock).toHaveBeenCalledWith("token-abc", "meeting-1");
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("preserves baseline output when additive fields are malformed and feature flags are off", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-1b",
      city_id: "seattle-wa",
      meeting_uid: "uid-1b",
      title: "Council Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-1b",
      published_at: "2026-02-25 19:00:00",
      summary: "Baseline detail still renders.",
      key_decisions: ["Approved downtown transit plan"],
      key_actions: ["Staff to publish implementation timeline"],
      notable_topics: ["Transit"],
      claims: [],
      planned: {
        generated_at: "2026-03-07T14:00:00Z",
        items: [],
      },
      outcomes: {
        authority_source: "minutes",
        items: [],
      },
      planned_outcome_mismatches: {
        items: [],
      },
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-1b" }),
      }),
    );

    const main = container.querySelector("main[data-render-mode]");
    const sectionHeadings = Array.from(
      container.querySelectorAll("section[aria-label] > h2"),
    ).map((heading) => heading.textContent);

    expect(main).toHaveAttribute("data-render-mode", "baseline");
    expect(main).toHaveAttribute("data-render-fallback", "planned_outcomes_flag_disabled");
    expect(screen.getByText("Baseline detail still renders.")).toBeInTheDocument();
    expect(sectionHeadings).toEqual([
      "Summary",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(screen.queryByRole("heading", { name: "Planned" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Outcomes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Mismatch indicators" })).not.toBeInTheDocument();
  });

  it("renders a prominent limited confidence banner when flagged", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-2",
      city_id: "seattle-wa",
      meeting_uid: "uid-2",
      title: "Budget Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "limited_confidence",
      confidence_label: "limited_confidence",
      reader_low_confidence: true,
      publication_id: null,
      published_at: null,
      summary: null,
      key_decisions: [],
      key_actions: [],
      notable_topics: [],
      claims: [],
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-2" }),
      }),
    );

    expect(screen.getByRole("alert", { name: "Confidence warning" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Limited confidence" })).toBeInTheDocument();
    expect(
      screen.getByText("Status: limited_confidence · Confidence: limited_confidence"),
    ).toBeInTheDocument();
    expect(screen.getByText("Summary is not available yet.")).toBeInTheDocument();
    expect(screen.getByText("No key decisions available.")).toBeInTheDocument();
    expect(screen.getByText("No key actions available.")).toBeInTheDocument();
    expect(screen.getByText("No notable topics available.")).toBeInTheDocument();
    expect(screen.getByText("No evidence references available.")).toBeInTheDocument();
  });

  it("renders an error state when detail fetch fails", async () => {
    fetchMeetingDetailMock.mockRejectedValueOnce(new Error("Service unavailable"));

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-3" }),
      }),
    );

    expect(screen.getByRole("heading", { name: "Meeting detail" })).toBeInTheDocument();
    expect(
      screen.getByText("Unable to load meeting detail. Service unavailable"),
    ).toBeInTheDocument();
  });

  it("resolves additive mode when flags are on and additive payloads are complete", async () => {
    process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = "true";
    process.env[MEETING_DETAIL_MISMATCH_SIGNALS_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-4",
      city_id: "seattle-wa",
      meeting_uid: "uid-4",
      title: "Transit Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-4",
      published_at: "2026-02-25 19:00:00",
      summary: "Council reviewed transit procurement.",
      key_decisions: ["Accepted report"],
      key_actions: ["Staff to return with revisions"],
      notable_topics: ["Transit"],
      claims: [],
      planned: {
        generated_at: "2026-03-07T14:00:00Z",
        source_coverage: {
          minutes: "present",
          agenda: "present",
          packet: "present",
        },
        items: [
          {
            planned_id: "planned-4",
            title: "Approve transit procurement",
            category: "procurement",
            status: "planned",
            confidence: "high",
            evidence_references_v2: [],
          },
        ],
      },
      outcomes: {
        generated_at: "2026-03-07T14:05:00Z",
        authority_source: "minutes",
        items: [
          {
            outcome_id: "outcome-4",
            title: "Transit procurement deferred",
            result: "deferred",
            confidence: "high",
            evidence_references_v2: [],
          },
        ],
      },
      planned_outcome_mismatches: {
        summary: {
          total: 1,
          high: 1,
          medium: 0,
          low: 0,
        },
        items: [
          {
            mismatch_id: "mismatch-4",
            planned_id: "planned-4",
            outcome_id: "outcome-4",
            severity: "high",
            mismatch_type: "disposition_change",
            description: "Deferred instead of approved.",
            reason_codes: ["outcome_changed"],
            evidence_references_v2: [
              {
                evidence_id: "ev-4",
                document_id: "doc-4",
                document_kind: "minutes",
                artifact_id: "artifact-4",
                section_path: "minutes.section.7",
                page_start: 3,
                page_end: 3,
                char_start: 44,
                char_end: 104,
                precision: "span",
                confidence: "high",
                excerpt: "Council deferred the transit procurement item pending revisions.",
              },
            ],
          },
        ],
      },
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-4" }),
      }),
    );

    const main = container.querySelector("main[data-render-mode]");
    const plannedSection = screen.getByRole("region", { name: "Planned" });
    const outcomesSection = screen.getByRole("region", { name: "Outcomes" });
    const sectionHeadings = Array.from(
      container.querySelectorAll("section[aria-label] > h2"),
    ).map((heading) => heading.textContent);

    expect(main).toHaveAttribute("data-render-mode", "additive");
    expect(main).toHaveAttribute("data-mismatch-signals", "enabled");
    expect(main).not.toHaveAttribute("data-render-fallback");
    expect(sectionHeadings).toEqual([
      "Summary",
      "Planned",
      "Outcomes",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(within(plannedSection).getByText("2026-03-07T14:00:00Z")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Approve transit procurement")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Procurement")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Agenda and packet items")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Source coverage")).toBeInTheDocument();
    expect(within(plannedSection).getByText("High")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Agenda")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Packet")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Minutes")).toBeInTheDocument();
    expect(within(outcomesSection).getByText("2026-03-07T14:05:00Z")).toBeInTheDocument();
    expect(within(outcomesSection).getByText("Transit procurement deferred")).toBeInTheDocument();
    expect(within(outcomesSection).getByText("Deferred")).toBeInTheDocument();
    expect(within(outcomesSection).getByText("Minutes")).toBeInTheDocument();
  });

  it("renders additive placeholders when planned and outcomes subfields are sparse", async () => {
    process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-4b",
      city_id: "seattle-wa",
      meeting_uid: "uid-4b",
      title: "Transit Session Follow-up",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "medium",
      reader_low_confidence: false,
      publication_id: "publication-4b",
      published_at: "2026-02-25 19:00:00",
      summary: "Council reviewed transit follow-up work.",
      key_decisions: [],
      key_actions: [],
      notable_topics: ["Transit"],
      claims: [],
      planned: {
        generated_at: "",
        source_coverage: {
          minutes: "missing",
          agenda: "present",
          packet: "missing",
        },
        items: [
          {
            planned_id: "planned-4b",
            title: "",
            category: "",
            status: "",
            confidence: "low",
            evidence_references_v2: [],
          },
        ],
      },
      outcomes: {
        generated_at: "",
        authority_source: "minutes",
        items: [
          {
            outcome_id: "outcome-4b",
            title: "",
            result: "",
            confidence: "medium",
            evidence_references_v2: [],
          },
        ],
      },
      planned_outcome_mismatches: {
        summary: {
          total: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        items: [],
      },
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-4b" }),
      }),
    );

    const main = container.querySelector("main[data-render-mode]");
    const plannedSection = screen.getByRole("region", { name: "Planned" });
    const outcomesSection = screen.getByRole("region", { name: "Outcomes" });

    expect(main).toHaveAttribute("data-render-mode", "additive");
    expect(main).not.toHaveAttribute("data-render-fallback");
    expect(within(plannedSection).getByText("Unavailable")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Untitled planned item")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Category unavailable")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Status unavailable")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Low")).toBeInTheDocument();
    expect(within(outcomesSection).getByText("Untitled outcome")).toBeInTheDocument();
    expect(within(outcomesSection).getByText("Result unavailable")).toBeInTheDocument();
    expect(within(outcomesSection).getByText("Medium")).toBeInTheDocument();
  });

  it("falls back to baseline without a user-visible error when additive payloads are partial", async () => {
    process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = "true";
    process.env[MEETING_DETAIL_MISMATCH_SIGNALS_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-5",
      city_id: "seattle-wa",
      meeting_uid: "uid-5",
      title: "Utilities Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "medium",
      reader_low_confidence: false,
      publication_id: "publication-5",
      published_at: "2026-02-25 19:00:00",
      summary: "Council discussed utilities planning.",
      key_decisions: [],
      key_actions: [],
      notable_topics: ["Utilities"],
      claims: [],
      planned: {
        generated_at: "2026-03-07T14:00:00Z",
        source_coverage: {
          minutes: "missing",
          agenda: "present",
          packet: "present",
        },
        items: [
          {
            planned_id: "planned-5",
            title: "Rate adjustment resolution",
            category: "ordinance",
            status: "planned",
            confidence: "medium",
            evidence_references_v2: [],
          },
        ],
      },
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-5" }),
      }),
    );

    const main = container.querySelector("main[data-render-mode]");

    expect(main).toHaveAttribute("data-render-mode", "baseline");
    expect(main).toHaveAttribute("data-render-fallback", "missing_outcomes_block");
    expect(container.textContent).not.toContain("Unable to load meeting detail");
    expect(screen.getByText("Council discussed utilities planning.")).toBeInTheDocument();
  });

  it("falls back safely when additive payloads are structurally malformed", async () => {
    process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = "true";
    process.env[MEETING_DETAIL_MISMATCH_SIGNALS_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-5b",
      city_id: "seattle-wa",
      meeting_uid: "uid-5b",
      title: "Utilities Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "medium",
      reader_low_confidence: false,
      publication_id: "publication-5b",
      published_at: "2026-02-25 19:00:00",
      summary: "Malformed additive data should not break baseline rendering.",
      key_decisions: [],
      key_actions: [],
      notable_topics: ["Utilities"],
      claims: [],
      planned: {
        generated_at: "2026-03-07T14:00:00Z",
        items: [],
      },
      outcomes: {
        generated_at: "2026-03-07T14:05:00Z",
        authority_source: "minutes",
        items: [],
      },
      planned_outcome_mismatches: {
        summary: {
          total: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        items: [],
      },
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-5b" }),
      }),
    );

    const main = container.querySelector("main[data-render-mode]");

    expect(main).toHaveAttribute("data-render-mode", "baseline");
    expect(main).toHaveAttribute("data-render-fallback", "invalid_planned_block");
    expect(container.textContent).not.toContain("Unable to load meeting detail");
    expect(screen.getByText("Malformed additive data should not break baseline rendering.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Planned" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Outcomes" })).not.toBeInTheDocument();
  });

  it("renders an explicit neutral state when mismatch entries are unsupported", async () => {
    process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = "true";
    process.env[MEETING_DETAIL_MISMATCH_SIGNALS_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-6",
      city_id: "seattle-wa",
      meeting_uid: "uid-6",
      title: "Procurement Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-6",
      published_at: "2026-02-25 19:00:00",
      summary: "Council reviewed a procurement update.",
      key_decisions: [],
      key_actions: [],
      notable_topics: ["Procurement"],
      claims: [],
      planned: {
        generated_at: "2026-03-07T14:00:00Z",
        source_coverage: {
          minutes: "present",
          agenda: "present",
          packet: "present",
        },
        items: [
          {
            planned_id: "planned-6",
            title: "Approve procurement change order",
            category: "procurement",
            status: "planned",
            confidence: "medium",
            evidence_references_v2: [],
          },
        ],
      },
      outcomes: {
        generated_at: "2026-03-07T14:05:00Z",
        authority_source: "minutes",
        items: [
          {
            outcome_id: "outcome-6",
            title: "Procurement change order deferred",
            result: "deferred",
            confidence: "medium",
            evidence_references_v2: [],
          },
        ],
      },
      planned_outcome_mismatches: {
        summary: {
          total: 1,
          high: 0,
          medium: 1,
          low: 0,
        },
        items: [
          {
            mismatch_id: "mismatch-6",
            planned_id: "planned-6",
            outcome_id: "outcome-6",
            severity: "medium",
            mismatch_type: "disposition_change",
            description: "Deferred instead of approved.",
            reason_codes: ["outcome_changed"],
            evidence_references_v2: [],
          },
        ],
      },
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-6" }),
      }),
    );

    expect(screen.getByRole("heading", { name: "Mismatch indicators" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Mismatch comparisons are available, but none have evidence-backed support yet.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Deferred instead of approved.")).not.toBeInTheDocument();
  });

  it("renders an explicit empty state when no mismatches are present", async () => {
    process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = "true";
    process.env[MEETING_DETAIL_MISMATCH_SIGNALS_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-7",
      city_id: "seattle-wa",
      meeting_uid: "uid-7",
      title: "Land Use Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-7",
      published_at: "2026-02-25 19:00:00",
      summary: "Council completed the planned land use review.",
      key_decisions: ["Accepted land use review"],
      key_actions: [],
      notable_topics: ["Land use"],
      claims: [],
      planned: {
        generated_at: "2026-03-07T14:00:00Z",
        source_coverage: {
          minutes: "present",
          agenda: "present",
          packet: "present",
        },
        items: [
          {
            planned_id: "planned-7",
            title: "Review land use updates",
            category: "briefing",
            status: "planned",
            confidence: "high",
            evidence_references_v2: [],
          },
        ],
      },
      outcomes: {
        generated_at: "2026-03-07T14:05:00Z",
        authority_source: "minutes",
        items: [
          {
            outcome_id: "outcome-7",
            title: "Land use updates reviewed",
            result: "received",
            confidence: "high",
            evidence_references_v2: [],
          },
        ],
      },
      planned_outcome_mismatches: {
        summary: {
          total: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        items: [],
      },
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-7" }),
      }),
    );

    expect(screen.getByRole("heading", { name: "Mismatch indicators" })).toBeInTheDocument();
    expect(
      screen.getByText("No evidence-backed mismatches were detected for this meeting."),
    ).toBeInTheDocument();
  });
});

afterEach(() => {
  cleanup();
});

afterAll(() => {
  if (originalPlannedOutcomesFlag === undefined) {
    delete process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED;
  } else {
    process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED = originalPlannedOutcomesFlag;
  }

  if (originalMismatchSignalsFlag === undefined) {
    delete process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED;
  } else {
    process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED = originalMismatchSignalsFlag;
  }
});
