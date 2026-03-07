import {
  type MeetingDetailResponse,
  type MeetingOutcomeItem,
  type MeetingOutcomesBlock,
  type MeetingPlannedBlock,
  type MeetingPlannedItem,
  type MeetingPlannedOutcomeMismatchItem,
  type MeetingPlannedOutcomeMismatchesBlock,
} from "../models/meetings";

export const MEETING_DETAIL_PLANNED_OUTCOMES_FLAG =
  "NEXT_PUBLIC_ST022_UI_PLANNED_OUTCOMES_ENABLED";
export const MEETING_DETAIL_MISMATCH_SIGNALS_FLAG =
  "NEXT_PUBLIC_ST022_UI_MISMATCH_SIGNALS_ENABLED";

export type MeetingDetailRenderMode = "baseline" | "additive";

export type MeetingDetailFeatureFlags = {
  plannedOutcomesEnabled: boolean;
  mismatchSignalsEnabled: boolean;
};

export type MeetingDetailBlockContractState = "present" | "missing" | "invalid";

export type MeetingDetailModeFallbackReason =
  | "planned_outcomes_flag_disabled"
  | "missing_planned_block"
  | "invalid_planned_block"
  | "missing_outcomes_block"
  | "invalid_outcomes_block";

export type MeetingDetailMismatchFallbackReason =
  | "mismatch_flag_disabled"
  | "additive_mode_unavailable"
  | "missing_mismatch_block"
  | "invalid_mismatch_block";

export type MeetingDetailResolvedRenderState = {
  mode: MeetingDetailRenderMode;
  modeFallbackReason: MeetingDetailModeFallbackReason | null;
  mismatchSignalsEnabled: boolean;
  mismatchFallbackReason: MeetingDetailMismatchFallbackReason | null;
  flags: MeetingDetailFeatureFlags;
  contract: {
    planned: MeetingDetailBlockContractState;
    outcomes: MeetingDetailBlockContractState;
    mismatches: MeetingDetailBlockContractState;
  };
};

export function getMeetingDetailFeatureFlags(
  env: NodeJS.ProcessEnv = process.env,
): MeetingDetailFeatureFlags {
  const plannedOutcomesEnabled = env[MEETING_DETAIL_PLANNED_OUTCOMES_FLAG] === "true";
  const mismatchSignalsRequested = env[MEETING_DETAIL_MISMATCH_SIGNALS_FLAG] === "true";

  return {
    plannedOutcomesEnabled,
    mismatchSignalsEnabled: plannedOutcomesEnabled && mismatchSignalsRequested,
  };
}

export function resolveMeetingDetailRenderState(
  detail: MeetingDetailResponse,
  flags: MeetingDetailFeatureFlags,
): MeetingDetailResolvedRenderState {
  const planned = classifyPlannedBlock(detail.planned);
  const outcomes = classifyOutcomesBlock(detail.outcomes);
  const mismatches = classifyMismatchBlock(detail.planned_outcome_mismatches);

  if (!flags.plannedOutcomesEnabled) {
    return {
      mode: "baseline",
      modeFallbackReason: "planned_outcomes_flag_disabled",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "mismatch_flag_disabled",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  if (planned === "missing") {
    return {
      mode: "baseline",
      modeFallbackReason: "missing_planned_block",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "additive_mode_unavailable",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  if (planned === "invalid") {
    return {
      mode: "baseline",
      modeFallbackReason: "invalid_planned_block",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "additive_mode_unavailable",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  if (outcomes === "missing") {
    return {
      mode: "baseline",
      modeFallbackReason: "missing_outcomes_block",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "additive_mode_unavailable",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  if (outcomes === "invalid") {
    return {
      mode: "baseline",
      modeFallbackReason: "invalid_outcomes_block",
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "additive_mode_unavailable",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  if (!flags.mismatchSignalsEnabled) {
    return {
      mode: "additive",
      modeFallbackReason: null,
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "mismatch_flag_disabled",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  if (mismatches === "missing") {
    return {
      mode: "additive",
      modeFallbackReason: null,
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "missing_mismatch_block",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  if (mismatches === "invalid") {
    return {
      mode: "additive",
      modeFallbackReason: null,
      mismatchSignalsEnabled: false,
      mismatchFallbackReason: "invalid_mismatch_block",
      flags,
      contract: { planned, outcomes, mismatches },
    };
  }

  return {
    mode: "additive",
    modeFallbackReason: null,
    mismatchSignalsEnabled: true,
    mismatchFallbackReason: null,
    flags,
    contract: { planned, outcomes, mismatches },
  };
}

function classifyPlannedBlock(value: MeetingPlannedBlock | undefined): MeetingDetailBlockContractState {
  if (value === undefined) {
    return "missing";
  }

  return isPlannedBlock(value) ? "present" : "invalid";
}

function classifyOutcomesBlock(value: MeetingOutcomesBlock | undefined): MeetingDetailBlockContractState {
  if (value === undefined) {
    return "missing";
  }

  return isOutcomesBlock(value) ? "present" : "invalid";
}

function classifyMismatchBlock(
  value: MeetingPlannedOutcomeMismatchesBlock | undefined,
): MeetingDetailBlockContractState {
  if (value === undefined) {
    return "missing";
  }

  return isMismatchBlock(value) ? "present" : "invalid";
}

function isPlannedBlock(value: MeetingPlannedBlock): boolean {
  return (
    typeof value.generated_at === "string" &&
    isCoverageStatus(value.source_coverage.minutes) &&
    isCoverageStatus(value.source_coverage.agenda) &&
    isCoverageStatus(value.source_coverage.packet) &&
    Array.isArray(value.items) &&
    value.items.every(isPlannedItem)
  );
}

function isPlannedItem(value: MeetingPlannedItem): boolean {
  return (
    typeof value.planned_id === "string" &&
    typeof value.title === "string" &&
    typeof value.category === "string" &&
    typeof value.status === "string" &&
    isConfidenceLevel(value.confidence) &&
    isOptionalEvidenceReferences(value.evidence_references_v2)
  );
}

function isOutcomesBlock(value: MeetingOutcomesBlock): boolean {
  return (
    typeof value.generated_at === "string" &&
    value.authority_source === "minutes" &&
    Array.isArray(value.items) &&
    value.items.every(isOutcomeItem)
  );
}

function isOutcomeItem(value: MeetingOutcomeItem): boolean {
  return (
    typeof value.outcome_id === "string" &&
    typeof value.title === "string" &&
    typeof value.result === "string" &&
    isConfidenceLevel(value.confidence) &&
    isOptionalEvidenceReferences(value.evidence_references_v2)
  );
}

function isMismatchBlock(value: MeetingPlannedOutcomeMismatchesBlock): boolean {
  return (
    Number.isInteger(value.summary.total) &&
    Number.isInteger(value.summary.high) &&
    Number.isInteger(value.summary.medium) &&
    Number.isInteger(value.summary.low) &&
    Array.isArray(value.items) &&
    value.items.every(isMismatchItem)
  );
}

function isMismatchItem(value: MeetingPlannedOutcomeMismatchItem): boolean {
  return (
    typeof value.mismatch_id === "string" &&
    typeof value.planned_id === "string" &&
    (typeof value.outcome_id === "string" || value.outcome_id === null) &&
    isConfidenceLevel(value.severity) &&
    typeof value.mismatch_type === "string" &&
    typeof value.description === "string" &&
    Array.isArray(value.reason_codes) &&
    value.reason_codes.every((reasonCode) => typeof reasonCode === "string") &&
    isOptionalEvidenceReferences(value.evidence_references_v2)
  );
}

function isCoverageStatus(value: string): boolean {
  return value === "present" || value === "missing";
}

function isConfidenceLevel(value: string): boolean {
  return value === "high" || value === "medium" || value === "low";
}

function isOptionalEvidenceReferences(value: unknown): boolean {
  return value === undefined || Array.isArray(value);
}