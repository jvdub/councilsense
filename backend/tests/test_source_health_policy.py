from __future__ import annotations

import pytest

from councilsense.app.settings import (
    DEFAULT_MANUAL_REVIEW_CONFIDENCE_THRESHOLD,
    DEFAULT_WARN_CONFIDENCE_THRESHOLD,
    get_settings,
)
from councilsense.app.source_health_policy import (
    ConfidencePolicyConfig,
    SourceHealthPolicyInput,
    derive_source_health_status,
    evaluate_confidence_policy,
)


def test_evaluate_confidence_policy_returns_manual_review_when_signal_missing() -> None:
    decision = evaluate_confidence_policy(confidence_score=None)

    assert decision.outcome == "manual_review_needed"
    assert decision.manual_review_needed is True
    assert decision.reader_low_confidence is True
    assert decision.reason_code == "confidence_signal_missing"


def test_evaluate_confidence_policy_respects_pass_warn_and_manual_review_bands() -> None:
    config = ConfidencePolicyConfig(manual_review_threshold=0.6, warn_threshold=0.8)

    manual_review_decision = evaluate_confidence_policy(confidence_score=0.59, config=config)
    warn_decision = evaluate_confidence_policy(confidence_score=0.6, config=config)
    pass_decision = evaluate_confidence_policy(confidence_score=0.8, config=config)

    assert manual_review_decision.outcome == "manual_review_needed"
    assert manual_review_decision.reason_code == "confidence_below_manual_review_threshold"
    assert manual_review_decision.reader_low_confidence is True

    assert warn_decision.outcome == "warn"
    assert warn_decision.reason_code == "confidence_below_warn_threshold"
    assert warn_decision.reader_low_confidence is True

    assert pass_decision.outcome == "pass"
    assert pass_decision.reason_code == "confidence_pass"
    assert pass_decision.reader_low_confidence is False


def test_evaluate_confidence_policy_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="warn_threshold must be greater than or equal"):
        evaluate_confidence_policy(
            confidence_score=0.7,
            config=ConfidencePolicyConfig(manual_review_threshold=0.7, warn_threshold=0.6),
        )

    with pytest.raises(ValueError, match="confidence_score must be within the inclusive range"):
        evaluate_confidence_policy(confidence_score=1.1)


def test_derive_source_health_status_transitions_are_deterministic() -> None:
    assert (
        derive_source_health_status(
            SourceHealthPolicyInput(last_attempt_succeeded=None, failure_streak=0)
        )
        == "unknown"
    )
    assert (
        derive_source_health_status(
            SourceHealthPolicyInput(last_attempt_succeeded=True, failure_streak=0)
        )
        == "healthy"
    )
    assert (
        derive_source_health_status(
            SourceHealthPolicyInput(last_attempt_succeeded=False, failure_streak=1)
        )
        == "degraded"
    )
    assert (
        derive_source_health_status(
            SourceHealthPolicyInput(last_attempt_succeeded=False, failure_streak=3)
        )
        == "failing"
    )


def test_derive_source_health_status_rejects_negative_failure_streak() -> None:
    with pytest.raises(ValueError, match="failure_streak must be greater than or equal to 0"):
        derive_source_health_status(
            SourceHealthPolicyInput(last_attempt_succeeded=False, failure_streak=-1)
        )


def test_get_settings_uses_default_policy_thresholds_when_env_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MANUAL_REVIEW_CONFIDENCE_THRESHOLD", raising=False)
    monkeypatch.delenv("WARN_CONFIDENCE_THRESHOLD", raising=False)

    settings = get_settings()

    assert settings.manual_review_confidence_threshold == DEFAULT_MANUAL_REVIEW_CONFIDENCE_THRESHOLD
    assert settings.warn_confidence_threshold == DEFAULT_WARN_CONFIDENCE_THRESHOLD


def test_get_settings_parses_policy_thresholds_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUAL_REVIEW_CONFIDENCE_THRESHOLD", "0.55")
    monkeypatch.setenv("WARN_CONFIDENCE_THRESHOLD", "0.9")

    settings = get_settings()

    assert settings.manual_review_confidence_threshold == 0.55
    assert settings.warn_confidence_threshold == 0.9


def test_get_settings_rejects_invalid_policy_threshold_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUAL_REVIEW_CONFIDENCE_THRESHOLD", "abc")
    with pytest.raises(ValueError, match="MANUAL_REVIEW_CONFIDENCE_THRESHOLD must be a float"):
        get_settings()

    monkeypatch.setenv("MANUAL_REVIEW_CONFIDENCE_THRESHOLD", "0.9")
    monkeypatch.setenv("WARN_CONFIDENCE_THRESHOLD", "0.8")
    with pytest.raises(ValueError, match="WARN_CONFIDENCE_THRESHOLD must be greater than or equal"):
        get_settings()
