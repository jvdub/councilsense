import React from "react";

import { type MeetingClaim } from "../../../lib/models/meetings";

type EvidenceReferencesProps = {
  claims: MeetingClaim[];
};

export function EvidenceReferences({ claims }: EvidenceReferencesProps) {
  if (claims.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
        No evidence references available.
      </p>
    );
  }

  return (
    <ol className="space-y-4">
      {claims.map((claim) => (
        <li
          key={claim.id}
          id={`claim-${claim.id}`}
          className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
        >
          <p className="text-base font-medium text-slate-900">{claim.claim_text}</p>
          {claim.evidence.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600">No evidence excerpts for this claim.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {claim.evidence.map((pointer) => (
                <li key={pointer.id} className="rounded-2xl border border-white bg-white p-4 shadow-sm">
                  <p className="text-sm leading-6 text-slate-700">{pointer.excerpt}</p>
                  <p className="mt-3 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                    Artifact: {pointer.artifact_id} · Section:{" "}
                    {pointer.section_ref ? (
                      <a href={`#claim-${claim.id}`} className="text-cyan-700 hover:text-cyan-900 hover:underline">
                        {pointer.section_ref}
                      </a>
                    ) : (
                      "not specified"
                    )}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  );
}
