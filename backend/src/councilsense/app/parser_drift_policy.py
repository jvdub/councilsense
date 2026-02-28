from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParserDriftComparisonInput:
    baseline_parser_name: str
    baseline_parser_version: str
    current_parser_name: str
    current_parser_version: str


def evaluate_parser_drift(comparison: ParserDriftComparisonInput) -> tuple[str, ...] | None:
    changed_fields: list[str] = []
    if comparison.baseline_parser_name != comparison.current_parser_name:
        changed_fields.append("parser_name")
    if comparison.baseline_parser_version != comparison.current_parser_version:
        changed_fields.append("parser_version")

    if not changed_fields:
        return None

    return tuple(changed_fields)
