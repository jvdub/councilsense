from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class StageQueueContractError(ValueError):
    def __init__(self, *, stage: str, field: str, reason: str) -> None:
        self.stage = stage
        self.field = field
        self.reason = reason
        super().__init__(f"Invalid {stage} queue payload field '{field}': {reason}")


def _required_string(*, payload: Mapping[str, object], stage: str, field: str) -> str:
    value = payload.get(field)
    if value is None:
        raise StageQueueContractError(stage=stage, field=field, reason="missing")
    if not isinstance(value, str):
        raise StageQueueContractError(stage=stage, field=field, reason="must be a string")
    normalized = value.strip()
    if not normalized:
        raise StageQueueContractError(stage=stage, field=field, reason="must be non-empty")
    return normalized


@dataclass(frozen=True)
class StageCorrelationIds:
    run_id: str
    city_id: str
    meeting_id: str


@dataclass(frozen=True)
class IngestStageMessage:
    run_id: str
    city_id: str
    meeting_id: str
    source_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> IngestStageMessage:
        return cls(
            run_id=_required_string(payload=payload, stage="ingest", field="run_id"),
            city_id=_required_string(payload=payload, stage="ingest", field="city_id"),
            meeting_id=_required_string(payload=payload, stage="ingest", field="meeting_id"),
            source_id=_required_string(payload=payload, stage="ingest", field="source_id"),
        )

    @property
    def correlation_ids(self) -> StageCorrelationIds:
        return StageCorrelationIds(run_id=self.run_id, city_id=self.city_id, meeting_id=self.meeting_id)

    def to_payload(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "city_id": self.city_id,
            "meeting_id": self.meeting_id,
            "source_id": self.source_id,
        }


@dataclass(frozen=True)
class ExtractStageMessage:
    run_id: str
    city_id: str
    meeting_id: str
    raw_artifact_uri: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> ExtractStageMessage:
        return cls(
            run_id=_required_string(payload=payload, stage="extract", field="run_id"),
            city_id=_required_string(payload=payload, stage="extract", field="city_id"),
            meeting_id=_required_string(payload=payload, stage="extract", field="meeting_id"),
            raw_artifact_uri=_required_string(payload=payload, stage="extract", field="raw_artifact_uri"),
        )

    @property
    def correlation_ids(self) -> StageCorrelationIds:
        return StageCorrelationIds(run_id=self.run_id, city_id=self.city_id, meeting_id=self.meeting_id)

    def to_payload(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "city_id": self.city_id,
            "meeting_id": self.meeting_id,
            "raw_artifact_uri": self.raw_artifact_uri,
        }


@dataclass(frozen=True)
class SummarizeStageMessage:
    run_id: str
    city_id: str
    meeting_id: str
    extracted_text_uri: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> SummarizeStageMessage:
        return cls(
            run_id=_required_string(payload=payload, stage="summarize", field="run_id"),
            city_id=_required_string(payload=payload, stage="summarize", field="city_id"),
            meeting_id=_required_string(payload=payload, stage="summarize", field="meeting_id"),
            extracted_text_uri=_required_string(payload=payload, stage="summarize", field="extracted_text_uri"),
        )

    @property
    def correlation_ids(self) -> StageCorrelationIds:
        return StageCorrelationIds(run_id=self.run_id, city_id=self.city_id, meeting_id=self.meeting_id)

    def to_payload(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "city_id": self.city_id,
            "meeting_id": self.meeting_id,
            "extracted_text_uri": self.extracted_text_uri,
        }


@dataclass(frozen=True)
class PublishStageMessage:
    run_id: str
    city_id: str
    meeting_id: str
    summary_markdown: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> PublishStageMessage:
        return cls(
            run_id=_required_string(payload=payload, stage="publish", field="run_id"),
            city_id=_required_string(payload=payload, stage="publish", field="city_id"),
            meeting_id=_required_string(payload=payload, stage="publish", field="meeting_id"),
            summary_markdown=_required_string(payload=payload, stage="publish", field="summary_markdown"),
        )

    @property
    def correlation_ids(self) -> StageCorrelationIds:
        return StageCorrelationIds(run_id=self.run_id, city_id=self.city_id, meeting_id=self.meeting_id)

    def to_payload(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "city_id": self.city_id,
            "meeting_id": self.meeting_id,
            "summary_markdown": self.summary_markdown,
        }


def produce_ingest_payload(*, run_id: str, city_id: str, meeting_id: str, source_id: str) -> dict[str, str]:
    message = IngestStageMessage(run_id=run_id, city_id=city_id, meeting_id=meeting_id, source_id=source_id)
    return IngestStageMessage.from_payload(message.to_payload()).to_payload()


def consume_ingest_payload(payload: Mapping[str, object]) -> IngestStageMessage:
    return IngestStageMessage.from_payload(payload)


def produce_extract_payload(*, run_id: str, city_id: str, meeting_id: str, raw_artifact_uri: str) -> dict[str, str]:
    message = ExtractStageMessage(
        run_id=run_id,
        city_id=city_id,
        meeting_id=meeting_id,
        raw_artifact_uri=raw_artifact_uri,
    )
    return ExtractStageMessage.from_payload(message.to_payload()).to_payload()


def consume_extract_payload(payload: Mapping[str, object]) -> ExtractStageMessage:
    return ExtractStageMessage.from_payload(payload)


def produce_summarize_payload(*, run_id: str, city_id: str, meeting_id: str, extracted_text_uri: str) -> dict[str, str]:
    message = SummarizeStageMessage(
        run_id=run_id,
        city_id=city_id,
        meeting_id=meeting_id,
        extracted_text_uri=extracted_text_uri,
    )
    return SummarizeStageMessage.from_payload(message.to_payload()).to_payload()


def consume_summarize_payload(payload: Mapping[str, object]) -> SummarizeStageMessage:
    return SummarizeStageMessage.from_payload(payload)


def produce_publish_payload(*, run_id: str, city_id: str, meeting_id: str, summary_markdown: str) -> dict[str, str]:
    message = PublishStageMessage(
        run_id=run_id,
        city_id=city_id,
        meeting_id=meeting_id,
        summary_markdown=summary_markdown,
    )
    return PublishStageMessage.from_payload(message.to_payload()).to_payload()


def consume_publish_payload(payload: Mapping[str, object]) -> PublishStageMessage:
    return PublishStageMessage.from_payload(payload)


def handoff_ingest_to_extract(
    ingest_message: IngestStageMessage,
    *,
    raw_artifact_uri: str,
) -> ExtractStageMessage:
    return ExtractStageMessage(
        run_id=ingest_message.run_id,
        city_id=ingest_message.city_id,
        meeting_id=ingest_message.meeting_id,
        raw_artifact_uri=_required_string(
            payload={"raw_artifact_uri": raw_artifact_uri},
            stage="extract",
            field="raw_artifact_uri",
        ),
    )


def handoff_extract_to_summarize(
    extract_message: ExtractStageMessage,
    *,
    extracted_text_uri: str,
) -> SummarizeStageMessage:
    return SummarizeStageMessage(
        run_id=extract_message.run_id,
        city_id=extract_message.city_id,
        meeting_id=extract_message.meeting_id,
        extracted_text_uri=_required_string(
            payload={"extracted_text_uri": extracted_text_uri},
            stage="summarize",
            field="extracted_text_uri",
        ),
    )


def handoff_summarize_to_publish(
    summarize_message: SummarizeStageMessage,
    *,
    summary_markdown: str,
) -> PublishStageMessage:
    return PublishStageMessage(
        run_id=summarize_message.run_id,
        city_id=summarize_message.city_id,
        meeting_id=summarize_message.meeting_id,
        summary_markdown=_required_string(
            payload={"summary_markdown": summary_markdown},
            stage="publish",
            field="summary_markdown",
        ),
    )