from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from councilsense.db import ConfidenceLabel, MeetingSummaryRepository, PublicationStatus, SummaryPublicationRecord


SUMMARIZATION_CONTRACT_VERSION = "st-005-v1"
EMPTY_SUMMARY_TEXT = "No summary available."


def _normalize_summary(summary: str) -> str:
    normalized = summary.strip()
    if not normalized:
        return EMPTY_SUMMARY_TEXT
    return normalized


def _normalize_section_items(items: Sequence[str] | None) -> tuple[str, ...]:
    if not items:
        return ()

    normalized_items: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized:
            normalized_items.append(normalized)
    return tuple(normalized_items)


def _encode_json_array(items: Sequence[str]) -> str:
    return json.dumps(list(items), ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class SummarizationOutput:
    summary: str
    key_decisions: tuple[str, ...]
    key_actions: tuple[str, ...]
    notable_topics: tuple[str, ...]
    contract_version: str = SUMMARIZATION_CONTRACT_VERSION

    @classmethod
    def from_sections(
        cls,
        *,
        summary: str,
        key_decisions: Sequence[str] | None,
        key_actions: Sequence[str] | None,
        notable_topics: Sequence[str] | None,
    ) -> SummarizationOutput:
        return cls(
            summary=_normalize_summary(summary),
            key_decisions=_normalize_section_items(key_decisions),
            key_actions=_normalize_section_items(key_actions),
            notable_topics=_normalize_section_items(notable_topics),
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> SummarizationOutput:
        summary = payload.get("summary")
        if not isinstance(summary, str):
            summary = ""

        return cls.from_sections(
            summary=summary,
            key_decisions=_read_string_list(payload, field="key_decisions"),
            key_actions=_read_string_list(payload, field="key_actions"),
            notable_topics=_read_string_list(payload, field="notable_topics"),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "summary": self.summary,
            "key_decisions": list(self.key_decisions),
            "key_actions": list(self.key_actions),
            "notable_topics": list(self.notable_topics),
        }


def _read_string_list(payload: Mapping[str, object], *, field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list):
        return ()

    raw_items: list[str] = []
    for item in value:
        if isinstance(item, str):
            raw_items.append(item)
    return _normalize_section_items(raw_items)


def persist_summarization_output(
    *,
    repository: MeetingSummaryRepository,
    publication_id: str,
    meeting_id: str,
    processing_run_id: str | None,
    publish_stage_outcome_id: str | None,
    version_no: int,
    publication_status: PublicationStatus,
    confidence_label: ConfidenceLabel,
    output: SummarizationOutput,
    published_at: str | None,
) -> SummaryPublicationRecord:
    return repository.create_publication(
        publication_id=publication_id,
        meeting_id=meeting_id,
        processing_run_id=processing_run_id,
        publish_stage_outcome_id=publish_stage_outcome_id,
        version_no=version_no,
        publication_status=publication_status,
        confidence_label=confidence_label,
        summary_text=output.summary,
        key_decisions_json=_encode_json_array(output.key_decisions),
        key_actions_json=_encode_json_array(output.key_actions),
        notable_topics_json=_encode_json_array(output.notable_topics),
        published_at=published_at,
    )