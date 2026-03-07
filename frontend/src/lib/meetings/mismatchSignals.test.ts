import { describe, expect, it } from "vitest";

import type { MeetingPlannedOutcomeMismatchItem } from "../models/meetings";
import {
  MISMATCH_SEVERITY_PRESENTATION,
  resolveMeetingMismatchIndicatorState,
} from "./mismatchSignals";

function buildMismatch(
  overrides: Partial<MeetingPlannedOutcomeMismatchItem> = {},
): MeetingPlannedOutcomeMismatchItem {
  return {
    mismatch_id: "mismatch-1",
    planned_id: "planned-1",
    outcome_id: "outcome-1",
    severity: "high",
    mismatch_type: "disposition_change",
    description: "Agenda planned approval but minutes record a deferment.",
    reason_codes: ["outcome_changed"],
    evidence_references_v2: [
      {
        evidence_id: "ev-1",
        document_id: "doc-1",
        document_kind: "minutes",
        artifact_id: "artifact-1",
        section_path: "minutes.section.4",
        page_start: 2,
        page_end: 2,
        char_start: 120,
        char_end: 188,
        precision: "span",
        confidence: "high",
        excerpt: "Council deferred the procurement item pending revisions.",
      },
    ],
    ...overrides,
  };
}

describe("mismatch signal resolution", () => {
  it("keeps deterministic severity labels for tests and UI rendering", () => {
    expect(MISMATCH_SEVERITY_PRESENTATION.high.label).toBe("High mismatch");
    expect(MISMATCH_SEVERITY_PRESENTATION.medium.label).toBe("Medium mismatch");
    expect(MISMATCH_SEVERITY_PRESENTATION.low.label).toBe("Low mismatch");
  });

  it("returns supported state when at least one mismatch is evidence-backed", () => {
    const result = resolveMeetingMismatchIndicatorState([
      buildMismatch(),
      buildMismatch({
        mismatch_id: "mismatch-2",
        severity: "medium",
        evidence_references_v2: [],
      }),
    ]);

    expect(result.kind).toBe("supported");
    expect(result.items).toHaveLength(1);
    expect(result.items[0]?.mismatch_id).toBe("mismatch-1");
  });

  it("returns unsupported state when mismatch entries exist without evidence-backed support", () => {
    const result = resolveMeetingMismatchIndicatorState([
      buildMismatch({ mismatch_id: "mismatch-2", evidence_references_v2: [] }),
    ]);

    expect(result).toEqual({
      kind: "unsupported",
      items: [],
    });
  });

  it("returns empty state when the mismatch list is empty", () => {
    const result = resolveMeetingMismatchIndicatorState([]);

    expect(result).toEqual({
      kind: "empty",
      items: [],
    });
  });
});