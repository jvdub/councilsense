from __future__ import annotations

from dataclasses import dataclass
from datetime import date


EXPECTED_SOURCE_TYPES: tuple[str, ...] = ("minutes", "agenda", "packet")


@dataclass(frozen=True)
class MeetingCandidate:
    meeting_id: str
    title: str
    candidate_url: str
    meeting_date_iso: str | None
    score: int


@dataclass(frozen=True)
class SourceRegistration:
    source_id: str
    source_type: str
    source_url: str
    enabled: bool = True


@dataclass(frozen=True)
class ResolvedBundleSource:
    source_type: str
    source_id: str | None
    source_url: str | None
    resolution: str


@dataclass(frozen=True)
class BundlePlannerDiagnostic:
    code: str
    meeting_id: str | None
    source_type: str | None
    detail: str


@dataclass(frozen=True)
class MeetingBundlePlan:
    bundle_id: str
    city_id: str
    meeting_id: str
    title: str
    candidate_url: str
    meeting_date_iso: str | None
    expected_sources: tuple[ResolvedBundleSource, ...]


@dataclass(frozen=True)
class BundlePlannerResult:
    bundles: tuple[MeetingBundlePlan, ...]
    diagnostics: tuple[BundlePlannerDiagnostic, ...]


def plan_meeting_bundles(
    *,
    city_id: str,
    meeting_candidates: tuple[MeetingCandidate, ...],
    source_registrations: tuple[SourceRegistration, ...],
) -> BundlePlannerResult:
    diagnostics: list[BundlePlannerDiagnostic] = []
    source_map = _resolve_source_map(source_registrations=source_registrations, diagnostics=diagnostics)

    candidates_by_meeting_id: dict[str, list[MeetingCandidate]] = {}
    for candidate in meeting_candidates:
        normalized_candidate = _normalize_candidate(candidate)
        if normalized_candidate is None:
            diagnostics.append(
                BundlePlannerDiagnostic(
                    code="candidate_skipped_invalid",
                    meeting_id=(candidate.meeting_id.strip() or None),
                    source_type=None,
                    detail="meeting_id, title, and candidate_url are required",
                )
            )
            continue
        candidates_by_meeting_id.setdefault(normalized_candidate.meeting_id, []).append(normalized_candidate)

    selected_candidates: list[MeetingCandidate] = []
    for meeting_id in sorted(candidates_by_meeting_id):
        group = candidates_by_meeting_id[meeting_id]
        selected = sorted(group, key=_candidate_rank_key, reverse=True)[0]
        selected_candidates.append(selected)
        if len(group) > 1:
            diagnostics.append(
                BundlePlannerDiagnostic(
                    code="candidate_resolution_tie_break_applied",
                    meeting_id=meeting_id,
                    source_type=None,
                    detail=(
                        f"selected candidate_url={selected.candidate_url} from {len(group)} candidates"
                    ),
                )
            )

    bundles: list[MeetingBundlePlan] = []
    for candidate in sorted(selected_candidates, key=_bundle_order_key):
        expected_sources, missing_types = _resolve_expected_sources(source_map=source_map)
        if len(missing_types) == len(EXPECTED_SOURCE_TYPES):
            diagnostics.append(
                BundlePlannerDiagnostic(
                    code="candidate_skipped_no_expected_sources_registered",
                    meeting_id=candidate.meeting_id,
                    source_type=None,
                    detail="minutes, agenda, and packet registrations are all missing",
                )
            )
            continue

        if missing_types:
            diagnostics.append(
                BundlePlannerDiagnostic(
                    code="bundle_partial_source_scope",
                    meeting_id=candidate.meeting_id,
                    source_type=None,
                    detail=f"missing source registrations: {', '.join(missing_types)}",
                )
            )

        bundles.append(
            MeetingBundlePlan(
                bundle_id=f"bundle:{city_id}:{candidate.meeting_id}",
                city_id=city_id,
                meeting_id=candidate.meeting_id,
                title=candidate.title,
                candidate_url=candidate.candidate_url,
                meeting_date_iso=candidate.meeting_date_iso,
                expected_sources=expected_sources,
            )
        )

    diagnostics.sort(
        key=lambda item: (
            item.code,
            item.meeting_id or "",
            item.source_type or "",
            item.detail,
        )
    )
    return BundlePlannerResult(bundles=tuple(bundles), diagnostics=tuple(diagnostics))


def _resolve_source_map(
    *,
    source_registrations: tuple[SourceRegistration, ...],
    diagnostics: list[BundlePlannerDiagnostic],
) -> dict[str, SourceRegistration]:
    grouped: dict[str, list[SourceRegistration]] = {source_type: [] for source_type in EXPECTED_SOURCE_TYPES}

    for registration in source_registrations:
        source_type = registration.source_type.strip().lower()
        if source_type not in grouped or not registration.enabled:
            continue
        grouped[source_type].append(
            SourceRegistration(
                source_id=registration.source_id.strip(),
                source_type=source_type,
                source_url=registration.source_url.strip(),
                enabled=True,
            )
        )

    resolved: dict[str, SourceRegistration] = {}
    for source_type in EXPECTED_SOURCE_TYPES:
        candidates = sorted(grouped[source_type], key=lambda item: (item.source_id, item.source_url))
        if not candidates:
            continue
        if len(candidates) > 1:
            diagnostics.append(
                BundlePlannerDiagnostic(
                    code="source_registration_duplicate_type_resolved",
                    meeting_id=None,
                    source_type=source_type,
                    detail=f"selected source_id={candidates[0].source_id} from {len(candidates)} registrations",
                )
            )
        resolved[source_type] = candidates[0]
    return resolved


def _resolve_expected_sources(*, source_map: dict[str, SourceRegistration]) -> tuple[tuple[ResolvedBundleSource, ...], list[str]]:
    expected: list[ResolvedBundleSource] = []
    missing_types: list[str] = []
    for source_type in EXPECTED_SOURCE_TYPES:
        resolved = source_map.get(source_type)
        if resolved is None:
            missing_types.append(source_type)
            expected.append(
                ResolvedBundleSource(
                    source_type=source_type,
                    source_id=None,
                    source_url=None,
                    resolution="missing_registration",
                )
            )
            continue
        expected.append(
            ResolvedBundleSource(
                source_type=source_type,
                source_id=resolved.source_id,
                source_url=resolved.source_url,
                resolution="resolved",
            )
        )
    return (tuple(expected), missing_types)


def _normalize_candidate(candidate: MeetingCandidate) -> MeetingCandidate | None:
    meeting_id = candidate.meeting_id.strip()
    title = candidate.title.strip()
    candidate_url = candidate.candidate_url.strip()
    if not meeting_id or not title or not candidate_url:
        return None

    normalized_date = _normalize_date(candidate.meeting_date_iso)
    return MeetingCandidate(
        meeting_id=meeting_id,
        title=title,
        candidate_url=candidate_url,
        meeting_date_iso=normalized_date,
        score=int(candidate.score),
    )


def _normalize_date(raw_date: str | None) -> str | None:
    if raw_date is None:
        return None
    value = raw_date.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _candidate_rank_key(candidate: MeetingCandidate) -> tuple[int, str, int, str, str]:
    date_value = candidate.meeting_date_iso or ""
    return (
        1 if candidate.meeting_date_iso is not None else 0,
        date_value,
        candidate.score,
        candidate.candidate_url,
        candidate.title,
    )


def _bundle_order_key(candidate: MeetingCandidate) -> tuple[int, str, str, str]:
    date_value = candidate.meeting_date_iso or ""
    return (
        1 if candidate.meeting_date_iso is not None else 0,
        date_value,
        candidate.meeting_id,
        candidate.candidate_url,
    )