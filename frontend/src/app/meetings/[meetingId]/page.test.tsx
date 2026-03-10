import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  afterAll,
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import MeetingDetailPage from "./page";
import {
  MEETING_DETAIL_MISMATCH_SIGNALS_FLAG,
  MEETING_DETAIL_PLANNED_OUTCOMES_FLAG,
} from "../../../lib/meetings/detailRenderMode";
import { MEETING_DETAIL_RESIDENT_SCAN_FLAG } from "../../../lib/meetings/residentScanMode";

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
const originalResidentScanFlag =
  process.env.NEXT_PUBLIC_ST034_UI_RESIDENT_SCAN_ENABLED;

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

function getLabelledSectionHeadings(container: HTMLElement) {
  return Array.from(container.querySelectorAll("section[aria-label] > h2")).map(
    (heading) => heading.textContent,
  );
}

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
    delete process.env.NEXT_PUBLIC_ST034_UI_RESIDENT_SCAN_ENABLED;
  });

  it("redirects unauthenticated users to sign-in", async () => {
    getAuthTokenFromCookieMock.mockResolvedValueOnce(null);

    await expect(
      MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-1" }),
      }),
    ).rejects.toThrow("REDIRECT:/auth/sign-in");
    expect(fetchBootstrapMock).not.toHaveBeenCalled();
  });

  it("renders summary, decisions, topics, and evidence references", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-1",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-1",
      title: "Council Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      meeting_date: "2026-02-25",
      body_name: "City Council",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/council-session.pdf",
      source_meeting_url: "https://example.org/meetings/council-session",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-1",
      published_at: "2026-02-25 19:00:00",
      summary: "Council approved the downtown transit plan.",
      key_decisions: ["Approved downtown transit plan"],
      key_actions: ["Staff to publish implementation timeline"],
      notable_topics: ["Transit", "Budget"],
      evidence_references_v2: [
        {
          evidence_id: "ev-1",
          document_id: "doc-1",
          document_kind: "minutes",
          artifact_id: "artifact-1",
          section_path: "minutes/section/4",
          page_start: null,
          page_end: null,
          char_start: 12,
          char_end: 80,
          precision: "span",
          confidence: "high",
          excerpt: "Council voted 6-1 to approve the transit plan.",
        },
      ],
      claims: [
        {
          id: "claim-1",
          claim_order: 1,
          claim_text: "Council approved the transit plan.",
          evidence: [
            {
              id: "pointer-1",
              artifact_id: "artifact-1",
              source_document_url:
                "https://example.org/minutes/council-session.pdf",
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

    expect(
      screen.getByRole("heading", { name: "Council Session" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Seattle")).toBeInTheDocument();
    expect(
      screen.getByText("City Council • February 25, 2026"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Summary" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Council approved the downtown transit plan."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Decisions and actions" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Approved downtown transit plan"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Staff to publish implementation timeline"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Notable topics" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Transit")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Evidence references" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Quick verification")).toBeInTheDocument();
    expect(screen.getAllByText("Minutes section 4").length).toBeGreaterThan(0);
    expect(
      screen.getByText("minutes/section/4 • chars 12-80 • Span precision"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Where to verify").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Technical reference").length).toBeGreaterThan(
      0,
    );
    expect(
      screen.queryByRole("heading", { name: "Planned" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Outcomes" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Suggested follow-up prompts" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Council approved the transit plan."),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Council voted 6-1 to approve the transit plan.")
        .length,
    ).toBe(2);
    expect(
      screen.getAllByRole("link", { name: "Open source record" }).length,
    ).toBeGreaterThan(0);
    for (const link of screen.getAllByRole("link", {
      name: "Open source record",
    })) {
      expect(link).toHaveAttribute(
        "href",
        "https://example.org/meetings/council-session",
      );
    }
    expect(
      screen.getByRole("link", { name: "Back to meetings" }),
    ).toHaveAttribute("href", "/meetings");
    expect(main).toHaveAttribute("data-render-mode", "baseline");
    expect(main).toHaveAttribute(
      "data-render-fallback",
      "planned_outcomes_flag_disabled",
    );
    expect(fetchMeetingDetailMock).toHaveBeenCalledWith(
      "token-abc",
      "meeting-1",
    );
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("renders bounded suggested prompts and links answers into prompt evidence groups", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-st035-1",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st035-1",
      title: "Council Session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "City Council",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/council-session.pdf",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-st035-1",
      published_at: "2026-03-09 19:00:00",
      summary: "Council approved the North Gateway rezoning application.",
      key_decisions: ["Approved the North Gateway rezoning application"],
      key_actions: ["Staff will publish the ordinance by April 15, 2026."],
      notable_topics: ["Land use"],
      claims: [],
      evidence_references_v2: [],
      suggested_prompts: [
        {
          prompt_id: "project_identity",
          prompt: "What project or item is this about?",
          answer: "North Gateway rezoning application.",
          evidence_references_v2: [
            {
              evidence_id: "ev-st035-1",
              document_id: "doc-st035-1",
              document_kind: "minutes",
              artifact_id: "artifact-st035-1",
              section_path: "minutes.section.4",
              page_start: null,
              page_end: null,
              char_start: 18,
              char_end: 122,
              precision: "offset",
              confidence: "high",
              excerpt:
                "Council approved the North Gateway rezoning application for the North Gateway District.",
            },
          ],
        },
        {
          prompt_id: "next_step",
          prompt: "What happens next?",
          answer: "Staff will publish the ordinance by April 15, 2026.",
          evidence_references_v2: [
            {
              evidence_id: "ev-st035-2",
              document_id: "doc-st035-2",
              document_kind: "minutes",
              artifact_id: "artifact-st035-2",
              section_path: "minutes.section.7",
              page_start: null,
              page_end: null,
              char_start: 40,
              char_end: 112,
              precision: "offset",
              confidence: "high",
              excerpt: "Staff will publish the ordinance by April 15, 2026.",
            },
          ],
        },
      ],
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st035-1" }),
      }),
    );

    const user = userEvent.setup();
    const promptSection = screen.getByRole("region", {
      name: "Suggested follow-up prompts",
    });
    const projectEvidenceLink = within(promptSection).getByRole("link", {
      name: "View evidence for What project or item is this about?",
    });
    const nextStepEvidenceLink = within(promptSection).getByRole("link", {
      name: "View evidence for What happens next?",
    });

    expect(
      within(promptSection).getByRole("heading", {
        level: 2,
        name: "Suggested follow-up prompts",
      }),
    ).toBeInTheDocument();
    expect(
      within(promptSection).getByText(
        "Quick answers to a fixed set of common follow-up questions from this meeting record.",
      ),
    ).toBeInTheDocument();
    expect(within(promptSection).getAllByText("Approved prompt")).toHaveLength(
      2,
    );
    expect(
      within(promptSection).getByText("What project or item is this about?"),
    ).toBeInTheDocument();
    expect(
      within(promptSection).getByText("North Gateway rezoning application."),
    ).toBeInTheDocument();
    expect(
      within(promptSection).getByText("What happens next?"),
    ).toBeInTheDocument();
    expect(
      within(promptSection).getByText(
        "Staff will publish the ordinance by April 15, 2026.",
      ),
    ).toBeInTheDocument();
    expect(projectEvidenceLink).toHaveAttribute(
      "href",
      "#suggested-prompt-evidence-project_identity",
    );
    expect(nextStepEvidenceLink).toHaveAttribute(
      "href",
      "#suggested-prompt-evidence-next_step",
    );
    projectEvidenceLink.focus();
    expect(projectEvidenceLink).toHaveFocus();
    await user.tab();
    expect(nextStepEvidenceLink).toHaveFocus();
    expect(
      screen.getByRole("heading", { name: "Suggested prompt evidence" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("What project or item is this about?").length,
    ).toBeGreaterThan(1);
    expect(screen.getByText("Minutes section 4")).toBeInTheDocument();
    expect(screen.getByText("Minutes section 7")).toBeInTheDocument();
  });

  it("omits the prompt section cleanly when suggested prompts are absent", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-st035-absent",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st035-absent",
      title: "Council Session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "City Council",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/council-session.pdf",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-st035-absent",
      published_at: "2026-03-09 19:00:00",
      summary: "Council discussed a work plan update.",
      key_decisions: [],
      key_actions: [],
      notable_topics: ["Operations"],
      claims: [],
      evidence_references_v2: [],
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st035-absent" }),
      }),
    );

    expect(
      screen.queryByRole("heading", { name: "Suggested follow-up prompts" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Suggested prompt evidence" }),
    ).not.toBeInTheDocument();
  });

  it("omits the prompt section cleanly when suggested prompts are empty", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-st035-2",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st035-2",
      title: "Council Session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "City Council",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/council-session.pdf",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-st035-2",
      published_at: "2026-03-09 19:00:00",
      summary: "Council discussed a work plan update.",
      key_decisions: [],
      key_actions: [],
      notable_topics: ["Operations"],
      claims: [],
      evidence_references_v2: [],
      suggested_prompts: [],
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st035-2" }),
      }),
    );

    expect(
      screen.queryByRole("heading", { name: "Suggested follow-up prompts" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Suggested prompt evidence" }),
    ).not.toBeInTheDocument();
  });

  it("renders resident impact scan cards when resident scan mode is enabled", async () => {
    process.env[MEETING_DETAIL_RESIDENT_SCAN_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-st034-1",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st034-1",
      title: "Growth and mobility session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "City Council",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/growth-mobility.pdf",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-st034-1",
      published_at: "2026-03-09 19:00:00",
      summary: "Council approved the North Gateway rezoning application.",
      key_decisions: ["Approved the North Gateway rezoning application"],
      key_actions: ["Staff to publish the ordinance"],
      notable_topics: ["Land use", "Housing"],
      claims: [],
      structured_relevance: {
        subject: {
          value: "North Gateway rezoning application",
          confidence: "high",
        },
        location: {
          value: "North Gateway District",
          confidence: "high",
        },
        action: {
          value: "approved",
          confidence: "high",
        },
        scale: {
          value: "142 acres and 893 units",
          confidence: "high",
        },
        impact_tags: [
          {
            tag: "housing",
            confidence: "high",
          },
          {
            tag: "land_use",
            confidence: "high",
          },
        ],
      },
      evidence_references_v2: [],
      outcomes: {
        generated_at: "2026-03-09T19:00:00Z",
        authority_source: "minutes",
        items: [
          {
            outcome_id: "outcome-st034-1",
            title: "North Gateway rezoning approved",
            result: "approved",
            confidence: "high",
            evidence_references_v2: [],
            subject: {
              value: "North Gateway rezoning application",
              confidence: "high",
            },
            location: {
              value: "North Gateway District",
              confidence: "high",
            },
            action: {
              value: "approved",
              confidence: "high",
            },
            scale: {
              value: "142 acres and 893 units",
              confidence: "high",
            },
            impact_tags: [
              {
                tag: "housing",
                confidence: "high",
              },
              {
                tag: "land_use",
                confidence: "high",
              },
            ],
          },
        ],
      },
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st034-1" }),
      }),
    );

    const main = container.querySelector("main[data-resident-scan-mode]");
    const sectionHeadings = Array.from(
      container.querySelectorAll("section[aria-label] > h2"),
    ).map((heading) => heading.textContent);
    const residentScanSection = screen.getByRole("region", {
      name: "Resident impact scan",
    });

    expect(main).toHaveAttribute("data-resident-scan-mode", "resident_scan");
    expect(sectionHeadings).toEqual([
      "Resident impact scan",
      "Summary",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(
      within(residentScanSection).getAllByText(
        "North Gateway rezoning application",
      ).length,
    ).toBeGreaterThan(0);
    expect(within(residentScanSection).getByText("What")).toBeInTheDocument();
    expect(within(residentScanSection).getByText("Where")).toBeInTheDocument();
    expect(within(residentScanSection).getByText("Action")).toBeInTheDocument();
    expect(within(residentScanSection).getByText("Scale")).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText("North Gateway District"),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText("approved"),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText("142 acres and 893 units"),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText("Impact tags"),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText("Housing"),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText("Land Use"),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText(
        "Supporting links are not available for this scan yet.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Summary" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Decisions and actions" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Notable topics" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Evidence references" }),
    ).toBeInTheDocument();
  });

  it("adds resident scan navigation affordances into supporting detail and evidence when links are available", async () => {
    process.env[MEETING_DETAIL_RESIDENT_SCAN_FLAG] = "true";
    process.env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-st034-3",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st034-3",
      title: "Growth and mobility session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "City Council",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/growth-mobility.pdf",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-st034-3",
      published_at: "2026-03-09 19:00:00",
      summary: "Council approved the North Gateway rezoning application.",
      key_decisions: ["Approved the North Gateway rezoning application"],
      key_actions: ["Staff to publish the ordinance"],
      notable_topics: ["Land use", "Housing"],
      claims: [],
      evidence_references_v2: [],
      structured_relevance: {
        subject: {
          value: "North Gateway rezoning application",
          confidence: "high",
        },
      },
      planned: {
        generated_at: "2026-03-09T18:55:00Z",
        source_coverage: {
          minutes: "present",
          agenda: "present",
          packet: "present",
        },
        items: [],
      },
      outcomes: {
        generated_at: "2026-03-09T19:00:00Z",
        authority_source: "minutes",
        items: [
          {
            outcome_id: "outcome-st034-3",
            title: "North Gateway rezoning approved",
            result: "approved",
            confidence: "high",
            evidence_references_v2: [],
            subject: {
              value: "North Gateway rezoning application",
              confidence: "high",
              evidence_references_v2: [
                {
                  evidence_id: "ev-st034-3",
                  document_id: "doc-st034-3",
                  document_kind: "minutes",
                  artifact_id: "artifact-st034-3",
                  section_path: "minutes.section.7",
                  page_start: 4,
                  page_end: 4,
                  char_start: 22,
                  char_end: 101,
                  precision: "span",
                  confidence: "high",
                  excerpt:
                    "Council approved the North Gateway rezoning application.",
                },
              ],
            },
            location: {
              value: "North Gateway District",
              confidence: "high",
            },
            action: {
              value: "approved",
              confidence: "high",
            },
            scale: {
              value: "142 acres and 893 units",
              confidence: "high",
            },
            impact_tags: [
              {
                tag: "housing",
                confidence: "high",
              },
            ],
          },
        ],
      },
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st034-3" }),
      }),
    );

    const user = userEvent.setup();
    const residentScanSection = screen.getByRole("region", {
      name: "Resident impact scan",
    });
    const supportingDetailLink = within(residentScanSection).getByRole("link", {
      name: "View supporting detail",
    });
    const evidenceLink = within(residentScanSection).getByRole("link", {
      name: "View evidence",
    });

    expect(
      within(residentScanSection).getByRole("heading", {
        level: 2,
        name: "Resident impact scan",
      }),
    ).toBeInTheDocument();
    expect(supportingDetailLink).toHaveAttribute(
      "href",
      "#outcome-item-outcome-st034-3",
    );
    expect(evidenceLink).toHaveAttribute(
      "href",
      "#resident-scan-evidence-outcome-outcome-st034-3",
    );
    supportingDetailLink.focus();
    expect(supportingDetailLink).toHaveFocus();
    await user.tab();
    expect(evidenceLink).toHaveFocus();
    expect(
      screen.getByRole("heading", { name: "Outcomes" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Resident scan evidence" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Minutes section 7 • page 4")).toBeInTheDocument();
  });

  it("renders neutral sparse-state messaging without broken resident evidence links", async () => {
    process.env[MEETING_DETAIL_RESIDENT_SCAN_FLAG] = "true";

    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-st034-4",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st034-4",
      title: "Utilities work session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "City Council",
      source_document_kind: "agenda",
      source_document_url: "https://example.org/agenda/utilities-session.pdf",
      status: "processed",
      confidence_label: "medium",
      reader_low_confidence: false,
      publication_id: "publication-st034-4",
      published_at: "2026-03-09 19:00:00",
      summary: "Agenda materials describe a utility contract work session.",
      key_decisions: [],
      key_actions: [],
      notable_topics: ["Utilities"],
      claims: [],
      evidence_references_v2: [],
      structured_relevance: {
        subject: {
          value: "Utility contract work session",
          confidence: "medium",
        },
      },
      planned: {
        generated_at: "2026-03-09T18:55:00Z",
        source_coverage: {
          minutes: "missing",
          agenda: "present",
          packet: "missing",
        },
        items: [],
      },
      outcomes: {
        generated_at: "2026-03-09T19:00:00Z",
        authority_source: "minutes",
        items: [],
      },
    });

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st034-4" }),
      }),
    );

    const residentScanSection = screen.getByRole("region", {
      name: "Resident impact scan",
    });

    expect(
      within(residentScanSection).getByText(
        "No specific impact tags were identified for this scan.",
      ),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText(
        "Some structured details were not available for this item.",
      ),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getByText("Partial"),
    ).toBeInTheDocument();
    expect(
      within(residentScanSection).getAllByText("Not specified"),
    ).toHaveLength(3);
    expect(
      within(residentScanSection).getByRole("link", { name: "View summary" }),
    ).toHaveAttribute("href", "#summary-section");
    expect(
      within(residentScanSection).queryByRole("link", {
        name: "View evidence",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Resident scan evidence" }),
    ).not.toBeInTheDocument();
  });

  it("preserves baseline meeting detail content when resident scan rendering is enabled additively", async () => {
    const detail = {
      id: "meeting-st034-parity",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st034-parity",
      title: "Neighborhood parking session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "Transportation Committee",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/parking-session.pdf",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-st034-parity",
      published_at: "2026-03-09 19:00:00",
      summary: "Council reviewed neighborhood parking changes near schools.",
      key_decisions: ["Accepted the parking update"],
      key_actions: ["Staff to draft final curb-zone changes"],
      notable_topics: ["Traffic", "Schools"],
      claims: [],
      evidence_references_v2: [],
      structured_relevance: {
        subject: {
          value: "Neighborhood parking changes",
          confidence: "high",
        },
        location: {
          value: "School safety zones",
          confidence: "medium",
        },
      },
    };

    fetchMeetingDetailMock.mockResolvedValueOnce(detail);

    const baselineRender = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st034-parity" }),
      }),
    );

    const baselineMain = baselineRender.container.querySelector(
      "main[data-resident-scan-mode]",
    );
    const baselineHeadings = getLabelledSectionHeadings(
      baselineRender.container,
    );

    expect(baselineMain).toHaveAttribute("data-resident-scan-mode", "baseline");
    expect(
      screen.queryByRole("heading", { name: "Resident impact scan" }),
    ).not.toBeInTheDocument();
    expect(baselineHeadings).toEqual([
      "Summary",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(
      screen.getByText(
        "Council reviewed neighborhood parking changes near schools.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Accepted the parking update")).toBeInTheDocument();
    expect(
      screen.getByText("Staff to draft final curb-zone changes"),
    ).toBeInTheDocument();
    expect(screen.getByText("Traffic")).toBeInTheDocument();

    cleanup();
    process.env[MEETING_DETAIL_RESIDENT_SCAN_FLAG] = "true";
    fetchMeetingDetailMock.mockResolvedValueOnce(detail);

    const additiveRender = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st034-parity" }),
      }),
    );

    const additiveMain = additiveRender.container.querySelector(
      "main[data-resident-scan-mode]",
    );
    const additiveHeadings = getLabelledSectionHeadings(
      additiveRender.container,
    );

    expect(additiveMain).toHaveAttribute(
      "data-resident-scan-mode",
      "resident_scan",
    );
    expect(additiveHeadings).toEqual([
      "Resident impact scan",
      "Summary",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(additiveHeadings.slice(1)).toEqual(baselineHeadings);
    expect(
      screen.getByRole("region", { name: "Resident impact scan" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Council reviewed neighborhood parking changes near schools.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Accepted the parking update")).toBeInTheDocument();
    expect(
      screen.getByText("Staff to draft final curb-zone changes"),
    ).toBeInTheDocument();
    expect(screen.getByText("Traffic")).toBeInTheDocument();
  });

  it("suppresses resident impact scan cards when the resident scan flag is off", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-st034-2",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-st034-2",
      title: "Growth and mobility session",
      created_at: "2026-03-09 18:00:00",
      updated_at: "2026-03-09 19:00:00",
      meeting_date: "2026-03-09",
      body_name: "City Council",
      source_document_kind: "minutes",
      source_document_url: "https://example.org/minutes/growth-mobility.pdf",
      status: "processed",
      confidence_label: "high",
      reader_low_confidence: false,
      publication_id: "publication-st034-2",
      published_at: "2026-03-09 19:00:00",
      summary: "Council approved the North Gateway rezoning application.",
      key_decisions: ["Approved the North Gateway rezoning application"],
      key_actions: ["Staff to publish the ordinance"],
      notable_topics: ["Land use", "Housing"],
      claims: [],
      evidence_references_v2: [],
      structured_relevance: {
        subject: {
          value: "North Gateway rezoning application",
          confidence: "high",
        },
      },
    });

    const { container } = render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-st034-2" }),
      }),
    );

    const main = container.querySelector("main[data-resident-scan-mode]");

    expect(main).toHaveAttribute("data-resident-scan-mode", "baseline");
    expect(main).toHaveAttribute(
      "data-resident-scan-fallback",
      "resident_scan_flag_disabled",
    );
    expect(
      screen.queryByRole("heading", { name: "Resident impact scan" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Summary" }),
    ).toBeInTheDocument();
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
    expect(main).toHaveAttribute(
      "data-render-fallback",
      "planned_outcomes_flag_disabled",
    );
    expect(
      screen.getByText("Baseline detail still renders."),
    ).toBeInTheDocument();
    expect(sectionHeadings).toEqual([
      "Summary",
      "Decisions and actions",
      "Notable topics",
      "Evidence references",
    ]);
    expect(
      screen.queryByRole("heading", { name: "Planned" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Outcomes" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Mismatch indicators" }),
    ).not.toBeInTheDocument();
  });

  it("renders a prominent limited confidence banner when flagged", async () => {
    fetchMeetingDetailMock.mockResolvedValueOnce({
      id: "meeting-2",
      city_id: "seattle-wa",
      city_name: "Seattle",
      meeting_uid: "uid-2",
      title: "Budget Session",
      created_at: "2026-02-25 18:00:00",
      updated_at: "2026-02-25 19:00:00",
      meeting_date: "2026-02-25",
      body_name: "Budget Committee",
      source_document_kind: null,
      source_document_url: null,
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

    expect(
      screen.getByRole("alert", { name: "Confidence warning" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Limited confidence" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Status: Limited Confidence · Confidence: Limited Confidence",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Summary is not available yet."),
    ).toBeInTheDocument();
    expect(screen.getByText("No key decisions available.")).toBeInTheDocument();
    expect(screen.getByText("No key actions available.")).toBeInTheDocument();
    expect(
      screen.getByText("No notable topics available."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No evidence references available."),
    ).toBeInTheDocument();
  });

  it("renders an error state when detail fetch fails", async () => {
    fetchMeetingDetailMock.mockRejectedValueOnce(
      new Error("Service unavailable"),
    );

    render(
      await MeetingDetailPage({
        params: Promise.resolve({ meetingId: "meeting-3" }),
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Meeting detail" }),
    ).toBeInTheDocument();
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
                excerpt:
                  "Council deferred the transit procurement item pending revisions.",
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
    expect(
      within(plannedSection).getByText("2026-03-07T14:00:00Z"),
    ).toBeInTheDocument();
    expect(
      within(plannedSection).getByText("Approve transit procurement"),
    ).toBeInTheDocument();
    expect(within(plannedSection).getByText("Procurement")).toBeInTheDocument();
    expect(
      within(plannedSection).getByText("Agenda and packet items"),
    ).toBeInTheDocument();
    expect(
      within(plannedSection).getByText("Source coverage"),
    ).toBeInTheDocument();
    expect(within(plannedSection).getByText("High")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Agenda")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Packet")).toBeInTheDocument();
    expect(within(plannedSection).getByText("Minutes")).toBeInTheDocument();
    expect(
      within(outcomesSection).getByText("2026-03-07T14:05:00Z"),
    ).toBeInTheDocument();
    expect(
      within(outcomesSection).getByText("Transit procurement deferred"),
    ).toBeInTheDocument();
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
    expect(
      within(plannedSection).getByText("Untitled planned item"),
    ).toBeInTheDocument();
    expect(
      within(plannedSection).getByText("Category unavailable"),
    ).toBeInTheDocument();
    expect(
      within(plannedSection).getByText("Status unavailable"),
    ).toBeInTheDocument();
    expect(within(plannedSection).getByText("Low")).toBeInTheDocument();
    expect(
      within(outcomesSection).getByText("Untitled outcome"),
    ).toBeInTheDocument();
    expect(
      within(outcomesSection).getByText("Result unavailable"),
    ).toBeInTheDocument();
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
    expect(main).toHaveAttribute(
      "data-render-fallback",
      "missing_outcomes_block",
    );
    expect(container.textContent).not.toContain(
      "Unable to load meeting detail",
    );
    expect(
      screen.getByText("Council discussed utilities planning."),
    ).toBeInTheDocument();
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
    expect(main).toHaveAttribute(
      "data-render-fallback",
      "invalid_planned_block",
    );
    expect(container.textContent).not.toContain(
      "Unable to load meeting detail",
    );
    expect(
      screen.getByText(
        "Malformed additive data should not break baseline rendering.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Planned" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Outcomes" }),
    ).not.toBeInTheDocument();
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

    expect(
      screen.getByRole("heading", { name: "Mismatch indicators" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Mismatch comparisons are available, but none have evidence-backed support yet.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Deferred instead of approved."),
    ).not.toBeInTheDocument();
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

    expect(
      screen.getByRole("heading", { name: "Mismatch indicators" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "No evidence-backed mismatches were detected for this meeting.",
      ),
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
    process.env.NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED =
      originalPlannedOutcomesFlag;
  }

  if (originalMismatchSignalsFlag === undefined) {
    delete process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED;
  } else {
    process.env.NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED =
      originalMismatchSignalsFlag;
  }

  if (originalResidentScanFlag === undefined) {
    delete process.env.NEXT_PUBLIC_ST034_UI_RESIDENT_SCAN_ENABLED;
  } else {
    process.env.NEXT_PUBLIC_ST034_UI_RESIDENT_SCAN_ENABLED =
      originalResidentScanFlag;
  }
});
