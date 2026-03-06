import React from "react";

import { PRIVACY_POLICY_URL, TERMS_OF_SERVICE_URL } from "../lib/legal/links";

type LegalLinksProps = {
  label?: string;
};

export function LegalLinks({ label = "Legal" }: LegalLinksProps) {
  return (
    <nav aria-label={label} className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      <a
        href={PRIVACY_POLICY_URL}
        target="_blank"
        rel="noreferrer"
        className="font-medium text-cyan-700 transition hover:text-cyan-900 hover:underline"
      >
        Privacy policy
      </a>
      <span className="hidden text-slate-300 sm:inline">•</span>
      <a
        href={TERMS_OF_SERVICE_URL}
        target="_blank"
        rel="noreferrer"
        className="font-medium text-cyan-700 transition hover:text-cyan-900 hover:underline"
      >
        Terms of service
      </a>
    </nav>
  );
}