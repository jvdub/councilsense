import { type MeetingPlannedOutcomeMismatchItem } from "../models/meetings";

export const MISMATCH_SEVERITY_PRESENTATION = {
  high: {
    label: "High mismatch",
    badgeClassName: "border-rose-200 bg-rose-50 text-rose-700",
  },
  medium: {
    label: "Medium mismatch",
    badgeClassName: "border-amber-200 bg-amber-50 text-amber-700",
  },
  low: {
    label: "Low mismatch",
    badgeClassName: "border-slate-300 bg-slate-100 text-slate-700",
  },
} as const;

export type MeetingMismatchIndicatorState =
  | {
      kind: "supported";
      items: MeetingPlannedOutcomeMismatchItem[];
    }
  | {
      kind: "unsupported";
      items: [];
    }
  | {
      kind: "empty";
      items: [];
    };

export function resolveMeetingMismatchIndicatorState(
  items: MeetingPlannedOutcomeMismatchItem[],
): MeetingMismatchIndicatorState {
  if (items.length === 0) {
    return {
      kind: "empty",
      items: [],
    };
  }

  const supportedItems = items.filter(isEvidenceBackedMismatch);

  if (supportedItems.length === 0) {
    return {
      kind: "unsupported",
      items: [],
    };
  }

  return {
    kind: "supported",
    items: supportedItems,
  };
}

export function isEvidenceBackedMismatch(
  item: MeetingPlannedOutcomeMismatchItem,
): boolean {
  return item.evidence_references_v2.length > 0;
}