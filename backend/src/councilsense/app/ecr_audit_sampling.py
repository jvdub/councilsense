from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Iterable

ELIGIBLE_PUBLICATION_STATUSES = {"processed", "limited_confidence"}


@dataclass(frozen=True)
class AuditSampleCandidate:
    publication_id: str
    meeting_id: str
    city_id: str
    source_id: str
    publication_status: str
    published_at: datetime


@dataclass(frozen=True)
class MalformedSampleRecord:
    publication_id: str
    reason_code: str


@dataclass(frozen=True)
class WeeklyAuditSampleSelection:
    publication_id: str
    meeting_id: str
    city_id: str
    source_id: str


@dataclass(frozen=True)
class WeeklyAuditRepresentativeness:
    target_city_slots: int
    target_source_slots: int
    achieved_city_slots: int
    achieved_source_slots: int

    @property
    def is_degraded(self) -> bool:
        return self.achieved_city_slots < self.target_city_slots or self.achieved_source_slots < self.target_source_slots


@dataclass(frozen=True)
class WeeklyAuditSampleResult:
    window_start_utc: datetime
    window_end_utc: datetime
    seed: str
    sample_size_requested: int
    eligible_frame_count: int
    sample_size_actual: int
    selected: tuple[WeeklyAuditSampleSelection, ...]
    malformed_exclusions: tuple[MalformedSampleRecord, ...]
    representativeness: WeeklyAuditRepresentativeness


def build_weekly_sampling_seed(*, window_start_utc: datetime, seed_salt: str = "v1") -> str:
    _validate_window_start(window_start_utc)
    if not seed_salt.strip():
        raise ValueError("seed_salt must be non-empty")
    return f"st-015-weekly-ecr-audit|{window_start_utc.date().isoformat()}|{seed_salt.strip()}"


def select_weekly_audit_sample(
    candidates: Iterable[AuditSampleCandidate],
    *,
    window_start_utc: datetime,
    sample_size: int = 60,
    seed_salt: str = "v1",
    min_city_slots: int = 3,
    min_source_slots: int = 2,
) -> WeeklyAuditSampleResult:
    _validate_window_start(window_start_utc)
    if sample_size <= 0:
        raise ValueError("sample_size must be > 0")
    if min_city_slots < 0:
        raise ValueError("min_city_slots must be >= 0")
    if min_source_slots < 0:
        raise ValueError("min_source_slots must be >= 0")

    window_end_utc = window_start_utc + timedelta(days=7)
    seed = build_weekly_sampling_seed(window_start_utc=window_start_utc, seed_salt=seed_salt)

    eligible: list[AuditSampleCandidate] = []
    malformed: list[MalformedSampleRecord] = []

    for candidate in candidates:
        reason = _validation_reason(candidate)
        publication_id = candidate.publication_id.strip() if candidate.publication_id.strip() else "unknown"
        if reason is not None:
            malformed.append(MalformedSampleRecord(publication_id=publication_id, reason_code=reason))
            continue

        published_at_utc = candidate.published_at.astimezone(timezone.utc)
        if not (window_start_utc <= published_at_utc < window_end_utc):
            continue

        eligible.append(candidate)

    if not eligible:
        representativeness = WeeklyAuditRepresentativeness(
            target_city_slots=0,
            target_source_slots=0,
            achieved_city_slots=0,
            achieved_source_slots=0,
        )
        return WeeklyAuditSampleResult(
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            seed=seed,
            sample_size_requested=sample_size,
            eligible_frame_count=0,
            sample_size_actual=0,
            selected=(),
            malformed_exclusions=tuple(malformed),
            representativeness=representativeness,
        )

    eligible_sorted = sorted(eligible, key=lambda item: _stable_rank(seed=seed, publication_id=item.publication_id))
    sample_size_cap = min(sample_size, len(eligible_sorted))

    by_city = _bucketize(eligible_sorted, key="city_id")
    by_source = _bucketize(eligible_sorted, key="source_id")

    target_city_slots = min(min_city_slots, len(by_city), sample_size_cap)
    target_source_slots = min(min_source_slots, len(by_source), sample_size_cap)

    selected_ids: set[str] = set()
    selected: list[AuditSampleCandidate] = []

    for city_id in sorted(by_city.keys(), key=lambda city: (-len(by_city[city]), city)):
        if len({item.city_id for item in selected}) >= target_city_slots:
            break
        candidate = _first_unselected(by_city[city_id], selected_ids)
        if candidate is None:
            continue
        selected.append(candidate)
        selected_ids.add(candidate.publication_id)
        if len(selected) >= sample_size_cap:
            break

    for source_id in sorted(by_source.keys(), key=lambda source: (-len(by_source[source]), source)):
        if len({item.source_id for item in selected}) >= target_source_slots:
            break
        if len(selected) >= sample_size_cap:
            break
        candidate = _first_unselected(by_source[source_id], selected_ids)
        if candidate is None:
            continue
        selected.append(candidate)
        selected_ids.add(candidate.publication_id)

    for candidate in eligible_sorted:
        if len(selected) >= sample_size_cap:
            break
        if candidate.publication_id in selected_ids:
            continue
        selected.append(candidate)
        selected_ids.add(candidate.publication_id)

    selected_output = tuple(
        WeeklyAuditSampleSelection(
            publication_id=item.publication_id,
            meeting_id=item.meeting_id,
            city_id=item.city_id,
            source_id=item.source_id,
        )
        for item in selected
    )

    representativeness = WeeklyAuditRepresentativeness(
        target_city_slots=target_city_slots,
        target_source_slots=target_source_slots,
        achieved_city_slots=len({item.city_id for item in selected}),
        achieved_source_slots=len({item.source_id for item in selected}),
    )

    return WeeklyAuditSampleResult(
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        seed=seed,
        sample_size_requested=sample_size,
        eligible_frame_count=len(eligible_sorted),
        sample_size_actual=len(selected),
        selected=selected_output,
        malformed_exclusions=tuple(malformed),
        representativeness=representativeness,
    )


def _first_unselected(
    bucket: tuple[AuditSampleCandidate, ...],
    selected_ids: set[str],
) -> AuditSampleCandidate | None:
    for item in bucket:
        if item.publication_id not in selected_ids:
            return item
    return None


def _bucketize(
    candidates: list[AuditSampleCandidate],
    *,
    key: str,
) -> dict[str, tuple[AuditSampleCandidate, ...]]:
    buckets: dict[str, list[AuditSampleCandidate]] = {}
    for candidate in candidates:
        bucket_value = getattr(candidate, key)
        buckets.setdefault(bucket_value, []).append(candidate)
    return {name: tuple(items) for name, items in buckets.items()}


def _stable_rank(*, seed: str, publication_id: str) -> str:
    return hashlib.sha256(f"{seed}|{publication_id}".encode("utf-8")).hexdigest()


def _validate_window_start(window_start_utc: datetime) -> None:
    if window_start_utc.tzinfo is None:
        raise ValueError("window_start_utc must be timezone-aware")
    if window_start_utc.utcoffset() != timedelta(0):
        raise ValueError("window_start_utc must be in UTC")
    if window_start_utc.hour != 0 or window_start_utc.minute != 0 or window_start_utc.second != 0:
        raise ValueError("window_start_utc must be at 00:00:00")
    if window_start_utc.weekday() != 0:
        raise ValueError("window_start_utc must be a Monday")


def _validation_reason(candidate: AuditSampleCandidate) -> str | None:
    if not candidate.publication_id.strip():
        return "missing_publication_id"
    if not candidate.meeting_id.strip():
        return "missing_meeting_id"
    if not candidate.city_id.strip():
        return "missing_city_id"
    if not candidate.source_id.strip():
        return "missing_source_id"
    if candidate.published_at.tzinfo is None:
        return "missing_published_at"
    if candidate.published_at.utcoffset() is None:
        return "invalid_published_at_timezone"
    if candidate.publication_status not in ELIGIBLE_PUBLICATION_STATUSES:
        return "invalid_publication_status"
    return None
