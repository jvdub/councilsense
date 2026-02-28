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
    <section aria-label="Confidence warning" role="alert">
      <h2>Limited confidence</h2>
      <p>
        This meeting includes low-confidence content. Verify details against the
        evidence references.
      </p>
    </section>
  );
}
