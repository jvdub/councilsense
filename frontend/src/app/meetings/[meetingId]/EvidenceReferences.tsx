import React from "react";

import { type MeetingClaim } from "../../../lib/models/meetings";

type EvidenceReferencesProps = {
  claims: MeetingClaim[];
};

export function EvidenceReferences({ claims }: EvidenceReferencesProps) {
  if (claims.length === 0) {
    return <p>No evidence references available.</p>;
  }

  return (
    <ol>
      {claims.map((claim) => (
        <li key={claim.id} id={`claim-${claim.id}`}>
          <p>{claim.claim_text}</p>
          {claim.evidence.length === 0 ? (
            <p>No evidence excerpts for this claim.</p>
          ) : (
            <ul>
              {claim.evidence.map((pointer) => (
                <li key={pointer.id}>
                  <p>{pointer.excerpt}</p>
                  <p>
                    Artifact: {pointer.artifact_id} · Section:{" "}
                    {pointer.section_ref ? (
                      <a href={`#claim-${claim.id}`}>{pointer.section_ref}</a>
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
