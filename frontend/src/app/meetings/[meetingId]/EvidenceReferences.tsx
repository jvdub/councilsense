import React from "react";

import {
  type MeetingClaim,
  type MeetingEvidenceReferenceV2,
} from "../../../lib/models/meetings";
import {
  buildEvidenceLocator,
  buildEvidenceReferenceV2Locator,
  buildTechnicalEvidenceLocator,
  buildTechnicalEvidenceReferenceV2Locator,
  formatSourceKindLabel,
} from "../../../lib/meetings/presentation";

export type ResidentScanEvidenceGroup = {
  id: string;
  cardTitle: string;
  sourceLabel: string;
  entries: Array<{
    label: string;
    references: MeetingEvidenceReferenceV2[];
  }>;
};

export type SuggestedPromptEvidenceGroup = {
  id: string;
  prompt: string;
  answer: string;
  references: MeetingEvidenceReferenceV2[];
};

type EvidenceReferencesProps = {
  claims: MeetingClaim[];
  evidenceReferencesV2?: MeetingEvidenceReferenceV2[];
  residentScanEvidenceGroups?: ResidentScanEvidenceGroup[];
  promptEvidenceGroups?: SuggestedPromptEvidenceGroup[];
  sourceDocumentKind?: string | null;
  sourceDocumentUrl?: string | null;
};

export function EvidenceReferences({
  claims,
  evidenceReferencesV2 = [],
  residentScanEvidenceGroups = [],
  promptEvidenceGroups = [],
  sourceDocumentKind,
  sourceDocumentUrl,
}: EvidenceReferencesProps) {
  if (
    claims.length === 0 &&
    evidenceReferencesV2.length === 0 &&
    residentScanEvidenceGroups.length === 0 &&
    promptEvidenceGroups.length === 0
  ) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
        No evidence references available.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {evidenceReferencesV2.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
            Quick verification
          </h3>
          <ul className="mt-4 space-y-3">
            {evidenceReferencesV2.map((reference) => (
              <li
                key={reference.evidence_id}
                className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 shadow-sm"
              >
                <p className="text-sm leading-6 text-slate-700">{reference.excerpt}</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {sourceDocumentUrl ? (
                    <a
                      href={sourceDocumentUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-800 transition hover:border-cyan-300 hover:bg-cyan-100"
                    >
                      Open source record
                    </a>
                  ) : (
                    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                      Source link unavailable
                    </span>
                  )}
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                    {formatSourceKindLabel(reference.document_kind)}
                  </span>
                </div>
                <dl className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
                  <div>
                    <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Where to verify</dt>
                    <dd className="mt-1 text-sm text-slate-700">
                      {buildEvidenceReferenceV2Locator(reference)}
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Technical reference</dt>
                    <dd className="mt-1 text-sm text-slate-700">
                      {buildTechnicalEvidenceReferenceV2Locator(reference)}
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Confidence</dt>
                    <dd className="mt-1 text-sm text-slate-700">
                      {reference.confidence ? reference.confidence : "Unavailable"}
                    </dd>
                  </div>
                </dl>
                <p className="mt-3 text-xs text-slate-500">Source ID: {reference.artifact_id}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {residentScanEvidenceGroups.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
            Resident scan evidence
          </h3>
          <ul className="mt-4 space-y-4">
            {residentScanEvidenceGroups.map((group) => (
              <li
                key={group.id}
                id={group.id}
                className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-base font-medium text-slate-900">{group.cardTitle}</p>
                  <span className="inline-flex w-fit items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                    {group.sourceLabel}
                  </span>
                </div>

                <div className="mt-4 space-y-4">
                  {group.entries.map((entry) => (
                    <div key={`${group.id}:${entry.label}`}>
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {entry.label}
                      </p>
                      <ul className="mt-3 space-y-3">
                        {entry.references.map((reference) => (
                          <li
                            key={reference.evidence_id}
                            className="rounded-2xl border border-white bg-white p-4 shadow-sm"
                          >
                            <p className="text-sm leading-6 text-slate-700">{reference.excerpt}</p>
                            <div className="mt-4 flex flex-wrap gap-3">
                              {sourceDocumentUrl ? (
                                <a
                                  href={sourceDocumentUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-800 transition hover:border-cyan-300 hover:bg-cyan-100"
                                >
                                  Open source record
                                </a>
                              ) : (
                                <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                                  Source link unavailable
                                </span>
                              )}
                              <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                                {formatSourceKindLabel(reference.document_kind)}
                              </span>
                            </div>
                            <dl className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
                              <div>
                                <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Where to verify</dt>
                                <dd className="mt-1 text-sm text-slate-700">
                                  {buildEvidenceReferenceV2Locator(reference)}
                                </dd>
                              </div>
                              <div>
                                <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Technical reference</dt>
                                <dd className="mt-1 text-sm text-slate-700">
                                  {buildTechnicalEvidenceReferenceV2Locator(reference)}
                                </dd>
                              </div>
                              <div>
                                <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Confidence</dt>
                                <dd className="mt-1 text-sm text-slate-700">
                                  {reference.confidence ? reference.confidence : "Unavailable"}
                                </dd>
                              </div>
                            </dl>
                            <p className="mt-3 text-xs text-slate-500">Source ID: {reference.artifact_id}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {promptEvidenceGroups.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
            Suggested prompt evidence
          </h3>
          <ul className="mt-4 space-y-4">
            {promptEvidenceGroups.map((group) => (
              <li
                key={group.id}
                id={group.id}
                className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-base font-medium text-slate-900">{group.prompt}</p>
                  <span className="inline-flex w-fit items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                    Suggested prompt
                  </span>
                </div>

                <p className="mt-4 text-sm leading-6 text-slate-700">{group.answer}</p>

                <ul className="mt-4 space-y-3">
                  {group.references.map((reference) => (
                    <li
                      key={reference.evidence_id}
                      className="rounded-2xl border border-white bg-white p-4 shadow-sm"
                    >
                      <p className="text-sm leading-6 text-slate-700">{reference.excerpt}</p>
                      <div className="mt-4 flex flex-wrap gap-3">
                        {sourceDocumentUrl ? (
                          <a
                            href={sourceDocumentUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-800 transition hover:border-cyan-300 hover:bg-cyan-100"
                          >
                            Open source record
                          </a>
                        ) : (
                          <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                            Source link unavailable
                          </span>
                        )}
                        <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                          {formatSourceKindLabel(reference.document_kind)}
                        </span>
                      </div>
                      <dl className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
                        <div>
                          <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Where to verify</dt>
                          <dd className="mt-1 text-sm text-slate-700">
                            {buildEvidenceReferenceV2Locator(reference)}
                          </dd>
                        </div>
                        <div>
                          <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Technical reference</dt>
                          <dd className="mt-1 text-sm text-slate-700">
                            {buildTechnicalEvidenceReferenceV2Locator(reference)}
                          </dd>
                        </div>
                        <div>
                          <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Confidence</dt>
                          <dd className="mt-1 text-sm text-slate-700">
                            {reference.confidence ? reference.confidence : "Unavailable"}
                          </dd>
                        </div>
                      </dl>
                      <p className="mt-3 text-xs text-slate-500">Source ID: {reference.artifact_id}</p>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {claims.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
            Claim-by-claim evidence
          </h3>
          <ol className="mt-4 space-y-4">
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
                              Open source record
                            </a>
                          ) : (
                            <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                              Source link unavailable
                            </span>
                          )}
                        </div>
                        <dl className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-2">
                          <div>
                            <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Where to verify</dt>
                            <dd className="mt-1 text-sm text-slate-700">{buildEvidenceLocator(pointer)}</dd>
                          </div>
                          <div>
                            <dt className="font-semibold uppercase tracking-[0.16em] text-slate-400">Technical reference</dt>
                            <dd className="mt-1 text-sm text-slate-700">{buildTechnicalEvidenceLocator(pointer)}</dd>
                          </div>
                        </dl>
                        <p className="mt-3 text-xs text-slate-500">Source ID: {pointer.artifact_id}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}
