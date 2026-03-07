import React from "react";

import {
  MISMATCH_SEVERITY_PRESENTATION,
  resolveMeetingMismatchIndicatorState,
} from "../../../lib/meetings/mismatchSignals";
import { type MeetingPlannedOutcomeMismatchesBlock } from "../../../lib/models/meetings";

type MismatchIndicatorsProps = {
  mismatches: MeetingPlannedOutcomeMismatchesBlock;
};

export function MismatchIndicators({ mismatches }: MismatchIndicatorsProps) {
  const indicatorState = resolveMeetingMismatchIndicatorState(mismatches.items);

  return (
    <section
      aria-label="Mismatch indicators"
      className="rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-lg shadow-slate-200/60"
      data-mismatch-indicator-state={indicatorState.kind}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
            Mismatch indicators
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Signals appear only when mismatch comparisons include supporting
            evidence.
          </p>
        </div>
        <p className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Evidence-backed mismatches
        </p>
      </div>

      {indicatorState.kind === "supported" ? (
        <ul className="mt-6 space-y-3">
          {indicatorState.items.map((item) => {
            const severity = MISMATCH_SEVERITY_PRESENTATION[item.severity];

            return (
              <li
                key={item.mismatch_id}
                className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
                data-mismatch-id={item.mismatch_id}
                data-mismatch-severity={item.severity}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {item.mismatch_type.replaceAll("_", " ")}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {item.description}
                    </p>
                  </div>
                  <span
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${severity.badgeClassName}`}
                  >
                    {severity.label}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      ) : indicatorState.kind === "unsupported" ? (
        <p className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
          Mismatch comparisons are available, but none have evidence-backed
          support yet.
        </p>
      ) : (
        <p className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
          No evidence-backed mismatches were detected for this meeting.
        </p>
      )}
    </section>
  );
}
