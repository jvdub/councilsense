import React from "react";

type ConfidenceBannerProps = {
  confidenceLabel: string | null;
  readerLowConfidence: boolean;
};

export function ConfidenceBanner({
  confidenceLabel,
  readerLowConfidence,
}: ConfidenceBannerProps) {
  const isLimitedConfidence =
    readerLowConfidence || confidenceLabel === "limited_confidence";

  if (!isLimitedConfidence) {
    return null;
  }

  return (
    <section
      aria-label="Confidence warning"
      role="alert"
      className="rounded-3xl border border-amber-300 bg-amber-50 px-5 py-4 text-amber-950 shadow-sm"
    >
      <h2 className="text-lg font-semibold">Limited confidence</h2>
      <p className="mt-2 text-sm leading-6 text-amber-900">
        This meeting includes low-confidence content. Verify details against the
        evidence references.
      </p>
    </section>
  );
}
