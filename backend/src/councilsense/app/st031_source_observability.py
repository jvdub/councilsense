from __future__ import annotations

import inspect
import sqlite3
from collections.abc import Callable, Mapping
from datetime import UTC, datetime


SourceAwareMetricEmitter = Callable[..., None]

SOURCE_STAGE_OUTCOMES_TOTAL = "councilsense_source_stage_outcomes_total"
SOURCE_COVERAGE_RATIO = "councilsense_source_coverage_ratio"
SOURCE_CITATION_PRECISION_RATIO = "councilsense_source_citation_precision_ratio"
PIPELINE_DLQ_BACKLOG_COUNT = "councilsense_pipeline_dlq_backlog_count"
PIPELINE_DLQ_OLDEST_AGE_SECONDS = "councilsense_pipeline_dlq_oldest_age_seconds"

_ACTIVE_PIPELINE_DLQ_STATUSES: tuple[str, ...] = ("open", "triaged", "replay_ready")


def emit_source_stage_outcome(
    metric_emitter: SourceAwareMetricEmitter | None,
    *,
    stage: str,
    outcome: str,
    city_id: str,
    source_type: str | None,
    status: str,
) -> None:
    _emit_metric(
        metric_emitter,
        name=SOURCE_STAGE_OUTCOMES_TOTAL,
        stage=stage,
        outcome=outcome,
        value=1.0,
        labels={
            "city_id": _normalize_label_value(city_id, fallback="city-unknown"),
            "source_type": _normalize_source_type(source_type),
            "status": _normalize_label_value(status, fallback="unknown"),
        },
    )


def emit_source_coverage_ratio(
    metric_emitter: SourceAwareMetricEmitter | None,
    *,
    city_id: str,
    coverage_ratio: float,
) -> None:
    _emit_metric(
        metric_emitter,
        name=SOURCE_COVERAGE_RATIO,
        stage="compose",
        outcome="measured",
        value=coverage_ratio,
        labels={
            "city_id": _normalize_label_value(city_id, fallback="city-unknown"),
            "source_type": "bundle",
        },
    )


def emit_citation_precision_ratio(
    metric_emitter: SourceAwareMetricEmitter | None,
    *,
    city_id: str,
    citation_precision_ratio: float | None,
) -> None:
    measured = citation_precision_ratio is not None
    _emit_metric(
        metric_emitter,
        name=SOURCE_CITATION_PRECISION_RATIO,
        stage="summarize",
        outcome=("measured" if measured else "missing_inputs"),
        value=(citation_precision_ratio if citation_precision_ratio is not None else 0.0),
        labels={
            "city_id": _normalize_label_value(city_id, fallback="city-unknown"),
            "source_type": "bundle",
        },
    )


def emit_pipeline_dlq_snapshot(
    metric_emitter: SourceAwareMetricEmitter | None,
    *,
    connection: sqlite3.Connection,
    observed_at: datetime | None = None,
) -> None:
    if metric_emitter is None:
        return

    rows = connection.execute(
        f"""
        SELECT
            city_id,
            stage_name,
            source_id,
            source_type,
            COUNT(*),
            MIN(terminal_transitioned_at)
        FROM pipeline_dlq_entries
        WHERE status IN ({','.join('?' for _ in _ACTIVE_PIPELINE_DLQ_STATUSES)})
        GROUP BY city_id, stage_name, source_id, source_type
        ORDER BY city_id ASC, stage_name ASC, source_id ASC
        """,
        _ACTIVE_PIPELINE_DLQ_STATUSES,
    ).fetchall()
    if not rows:
        return

    current_time = (observed_at or datetime.now(UTC)).astimezone(UTC)
    for row in rows:
        city_id = _normalize_label_value(row[0], fallback="city-unknown")
        stage_name = _normalize_label_value(row[1], fallback="unknown")
        source_id = _normalize_label_value(row[2], fallback="source-unknown")
        source_type = _normalize_source_type(row[3])
        backlog_count = float(row[4])
        oldest_age_seconds = _age_seconds(observed_at=current_time, timestamp_value=row[5])
        labels = {
            "city_id": city_id,
            "source_id": source_id,
            "source_type": source_type,
        }
        _emit_metric(
            metric_emitter,
            name=PIPELINE_DLQ_BACKLOG_COUNT,
            stage=stage_name,
            outcome="backlog",
            value=backlog_count,
            labels=labels,
        )
        _emit_metric(
            metric_emitter,
            name=PIPELINE_DLQ_OLDEST_AGE_SECONDS,
            stage=stage_name,
            outcome="oldest_age",
            value=oldest_age_seconds,
            labels=labels,
        )


def _emit_metric(
    metric_emitter: SourceAwareMetricEmitter | None,
    *,
    name: str,
    stage: str,
    outcome: str,
    value: float,
    labels: Mapping[str, str] | None = None,
) -> None:
    if metric_emitter is None:
        return
    if _supports_label_argument(metric_emitter):
        metric_emitter(name, stage, outcome, value, dict(labels or {}))
        return
    metric_emitter(name, stage, outcome, value)


def _supports_label_argument(metric_emitter: SourceAwareMetricEmitter) -> bool:
    try:
        signature = inspect.signature(metric_emitter)
    except (TypeError, ValueError):
        return True

    positional = 0
    for parameter in signature.parameters.values():
        if parameter.kind in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }:
            positional += 1
            continue
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            return True
    return positional >= 5


def _normalize_source_type(value: object) -> str:
    normalized = _normalize_label_value(value, fallback="unknown")
    if normalized in {"minutes", "agenda", "packet", "bundle"}:
        return normalized
    return "unknown"


def _normalize_label_value(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = value.strip().lower()
    if not normalized:
        return fallback
    return normalized


def _age_seconds(*, observed_at: datetime, timestamp_value: object) -> float:
    if not isinstance(timestamp_value, str) or not timestamp_value.strip():
        return 0.0
    parsed = datetime.fromisoformat(timestamp_value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max((observed_at - parsed.astimezone(UTC)).total_seconds(), 0.0)