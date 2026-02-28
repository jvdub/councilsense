from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceHealthStatus = Literal["healthy", "degraded", "failing", "unknown"]
ConfidencePolicyOutcome = Literal["pass", "warn", "manual_review_needed"]


@dataclass(frozen=True)
class SourceHealthPolicyInput:
    last_attempt_succeeded: bool | None
    failure_streak: int


@dataclass(frozen=True)
class ConfidencePolicyConfig:
    manual_review_threshold: float = 0.6
    warn_threshold: float = 0.8

    def validate(self) -> None:
        _validate_threshold(name="manual_review_threshold", value=self.manual_review_threshold)
        _validate_threshold(name="warn_threshold", value=self.warn_threshold)
        if self.warn_threshold < self.manual_review_threshold:
            raise ValueError("warn_threshold must be greater than or equal to manual_review_threshold")


@dataclass(frozen=True)
class ConfidencePolicyDecision:
    outcome: ConfidencePolicyOutcome
    manual_review_needed: bool
    reader_low_confidence: bool
    reason_code: str
    confidence_score: float | None
    manual_review_threshold: float
    warn_threshold: float


def derive_source_health_status(policy_input: SourceHealthPolicyInput) -> SourceHealthStatus:
    if policy_input.failure_streak < 0:
        raise ValueError("failure_streak must be greater than or equal to 0")

    if policy_input.last_attempt_succeeded is None:
        return "unknown"

    if policy_input.last_attempt_succeeded:
        return "healthy"

    if policy_input.failure_streak >= 3:
        return "failing"

    return "degraded"


def evaluate_confidence_policy(
    *,
    confidence_score: float | None,
    config: ConfidencePolicyConfig | None = None,
) -> ConfidencePolicyDecision:
    effective_config = config or ConfidencePolicyConfig()
    effective_config.validate()

    if confidence_score is None:
        return ConfidencePolicyDecision(
            outcome="manual_review_needed",
            manual_review_needed=True,
            reader_low_confidence=True,
            reason_code="confidence_signal_missing",
            confidence_score=None,
            manual_review_threshold=effective_config.manual_review_threshold,
            warn_threshold=effective_config.warn_threshold,
        )

    _validate_threshold(name="confidence_score", value=confidence_score)

    if confidence_score < effective_config.manual_review_threshold:
        return ConfidencePolicyDecision(
            outcome="manual_review_needed",
            manual_review_needed=True,
            reader_low_confidence=True,
            reason_code="confidence_below_manual_review_threshold",
            confidence_score=confidence_score,
            manual_review_threshold=effective_config.manual_review_threshold,
            warn_threshold=effective_config.warn_threshold,
        )

    if confidence_score < effective_config.warn_threshold:
        return ConfidencePolicyDecision(
            outcome="warn",
            manual_review_needed=False,
            reader_low_confidence=True,
            reason_code="confidence_below_warn_threshold",
            confidence_score=confidence_score,
            manual_review_threshold=effective_config.manual_review_threshold,
            warn_threshold=effective_config.warn_threshold,
        )

    return ConfidencePolicyDecision(
        outcome="pass",
        manual_review_needed=False,
        reader_low_confidence=False,
        reason_code="confidence_pass",
        confidence_score=confidence_score,
        manual_review_threshold=effective_config.manual_review_threshold,
        warn_threshold=effective_config.warn_threshold,
    )


def _validate_threshold(*, name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be within the inclusive range [0.0, 1.0]")
