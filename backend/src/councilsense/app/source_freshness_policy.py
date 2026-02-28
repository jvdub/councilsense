from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import inf
from typing import Literal


FreshnessSeverity = Literal["warning", "critical"]


@dataclass(frozen=True)
class SourceFreshnessThresholdConfig:
    warning_age_hours: float
    critical_age_hours: float

    def validate(self) -> None:
        if self.warning_age_hours <= 0:
            raise ValueError("warning_age_hours must be greater than 0")
        if self.critical_age_hours <= 0:
            raise ValueError("critical_age_hours must be greater than 0")
        if self.critical_age_hours < self.warning_age_hours:
            raise ValueError("critical_age_hours must be greater than or equal to warning_age_hours")


@dataclass(frozen=True)
class SourceMaintenanceWindow:
    window_name: str
    starts_at: str
    ends_at: str
    city_id: str | None = None
    source_id: str | None = None

    def applies_to(self, *, city_id: str, source_id: str, evaluated_at: datetime) -> bool:
        if self.city_id is not None and self.city_id != city_id:
            return False
        if self.source_id is not None and self.source_id != source_id:
            return False

        start = parse_timestamp(self.starts_at)
        end = parse_timestamp(self.ends_at)
        return start <= evaluated_at <= end


@dataclass(frozen=True)
class SourceFreshnessPolicyConfig:
    default_thresholds: SourceFreshnessThresholdConfig = SourceFreshnessThresholdConfig(
        warning_age_hours=24.0,
        critical_age_hours=48.0,
    )
    profile_thresholds: dict[str, SourceFreshnessThresholdConfig] = field(default_factory=dict)
    source_type_profile_overrides: dict[str, str] = field(default_factory=dict)
    source_id_profile_overrides: dict[str, str] = field(default_factory=dict)
    maintenance_windows: tuple[SourceMaintenanceWindow, ...] = ()
    evaluation_window: str = "PT1H"

    def validate(self) -> None:
        self.default_thresholds.validate()
        for thresholds in self.profile_thresholds.values():
            thresholds.validate()

    def thresholds_for_source(self, *, source_id: str, source_type: str) -> SourceFreshnessThresholdConfig:
        profile_name = self.source_id_profile_overrides.get(source_id)
        if profile_name is None:
            profile_name = self.source_type_profile_overrides.get(source_type)
        if profile_name is None:
            return self.default_thresholds
        return self.profile_thresholds.get(profile_name, self.default_thresholds)


@dataclass(frozen=True)
class SourceFreshnessEvaluationInput:
    city_id: str
    source_id: str
    source_type: str
    evaluated_at: str
    last_success_at: str | None


@dataclass(frozen=True)
class SourceFreshnessDecision:
    severity: FreshnessSeverity
    last_success_age_hours: float
    threshold_age_hours: float
    suppressed: bool
    suppression_reason: str | None
    suppression_window_name: str | None
    suppression_window_starts_at: str | None
    suppression_window_ends_at: str | None


def evaluate_source_freshness(
    *,
    policy_input: SourceFreshnessEvaluationInput,
    config: SourceFreshnessPolicyConfig,
) -> SourceFreshnessDecision | None:
    config.validate()

    evaluated_at = parse_timestamp(policy_input.evaluated_at)
    thresholds = config.thresholds_for_source(source_id=policy_input.source_id, source_type=policy_input.source_type)

    last_success_age_hours = _calculate_last_success_age_hours(
        last_success_at=policy_input.last_success_at,
        evaluated_at=evaluated_at,
    )

    if last_success_age_hours < thresholds.warning_age_hours:
        return None

    severity: FreshnessSeverity = "warning"
    threshold_age_hours = thresholds.warning_age_hours

    if last_success_age_hours >= thresholds.critical_age_hours:
        severity = "critical"
        threshold_age_hours = thresholds.critical_age_hours

    for window in config.maintenance_windows:
        if window.applies_to(
            city_id=policy_input.city_id,
            source_id=policy_input.source_id,
            evaluated_at=evaluated_at,
        ):
            return SourceFreshnessDecision(
                severity=severity,
                last_success_age_hours=last_success_age_hours,
                threshold_age_hours=threshold_age_hours,
                suppressed=True,
                suppression_reason="planned_maintenance_window",
                suppression_window_name=window.window_name,
                suppression_window_starts_at=window.starts_at,
                suppression_window_ends_at=window.ends_at,
            )

    return SourceFreshnessDecision(
        severity=severity,
        last_success_age_hours=last_success_age_hours,
        threshold_age_hours=threshold_age_hours,
        suppressed=False,
        suppression_reason=None,
        suppression_window_name=None,
        suppression_window_starts_at=None,
        suppression_window_ends_at=None,
    )


def _calculate_last_success_age_hours(*, last_success_at: str | None, evaluated_at: datetime) -> float:
    if last_success_at is None:
        return inf

    delta_seconds = (evaluated_at - parse_timestamp(last_success_at)).total_seconds()
    if delta_seconds < 0:
        return 0.0
    return delta_seconds / 3600.0


def parse_timestamp(value: str) -> datetime:
    candidate = value.strip()
    if not candidate:
        raise ValueError("timestamp value must not be empty")

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
