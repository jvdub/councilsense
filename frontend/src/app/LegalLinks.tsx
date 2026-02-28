import React from "react";

import { PRIVACY_POLICY_URL, TERMS_OF_SERVICE_URL } from "../lib/legal/links";

type LegalLinksProps = {
  label?: string;
};

export function LegalLinks({ label = "Legal" }: LegalLinksProps) {
  return (
    <nav aria-label={label}>
      <a href={PRIVACY_POLICY_URL} target="_blank" rel="noreferrer">
        Privacy policy
      </a>{" "}
      <a href={TERMS_OF_SERVICE_URL} target="_blank" rel="noreferrer">
        Terms of service
      </a>
    </nav>
  );
}