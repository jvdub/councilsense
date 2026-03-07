import React from "react";

import { type MeetingClaim } from "../../../lib/models/meetings";
import {
  buildEvidenceLocator,
  formatSourceKindLabel,
} from "../../../lib/meetings/presentation";

type EvidenceReferencesProps = {
  claims: MeetingClaim[];
  sourceDocumentKind?: string | null;
};

export function EvidenceReferences({ claims, sourceDocumentKind }: EvidenceReferencesProps) {
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
                  <div className="mt-4 flex flex-wrap gap-3">
                    {pointer.source_document_url ? (
                      <a
                        href={pointer.source_document_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-800 transition hover:border-cyan-300 hover:bg-cyan-100"
                      >
                        Open {formatSourceKindLabel(sourceDocumentKind).toLowerCase()}
                      </a>
                    ) : (
                      <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                        Source link unavailable
                      </span>
                    )}
                  </div>
                  <dl className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-2">
                    <div>
                      <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Locator</dt>
                      <dd className="mt-1 text-sm text-slate-700">{buildEvidenceLocator(pointer)}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Artifact</dt>
                      <dd className="mt-1 text-sm text-slate-700">{pointer.artifact_id}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  );
}
