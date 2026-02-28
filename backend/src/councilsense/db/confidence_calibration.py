from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, cast


DEFAULT_CALIBRATION_POLICY_VERSION = "st015-calibration-policy-v1-default"


@dataclass(frozen=True)
class ConfidenceCalibrationPolicyRecord:
    version: str
    min_claim_count: int
    min_total_evidence_pointers: int
    min_evidence_coverage_rate: float
    max_evidence_gap_claims: int
    min_confidence_score: float | None
    source_audit_run_id: str | None
    created_from_reviewer_outcomes_json: str | None
    notes: str | None
    is_active: bool
    activated_at: str | None
    created_at: str
    updated_at: str


class ConfidenceCalibrationPolicyRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_active_policy(self) -> ConfidenceCalibrationPolicyRecord:
        row = self._connection.execute(
            """
            SELECT
                version,
                min_claim_count,
                min_total_evidence_pointers,
                min_evidence_coverage_rate,
                max_evidence_gap_claims,
                min_confidence_score,
                source_audit_run_id,
                created_from_reviewer_outcomes_json,
                notes,
                is_active,
                activated_at,
                created_at,
                updated_at
            FROM confidence_calibration_policies
            WHERE is_active = 1
            ORDER BY activated_at DESC, version DESC
            LIMIT 1
            """
        ).fetchone()
        if row is not None:
            return _to_policy_record(row)

        fallback_row = self._connection.execute(
            """
            SELECT
                version,
                min_claim_count,
                min_total_evidence_pointers,
                min_evidence_coverage_rate,
                max_evidence_gap_claims,
                min_confidence_score,
                source_audit_run_id,
                created_from_reviewer_outcomes_json,
                notes,
                is_active,
                activated_at,
                created_at,
                updated_at
            FROM confidence_calibration_policies
            ORDER BY created_at DESC, version DESC
            LIMIT 1
            """
        ).fetchone()
        if fallback_row is None:
            raise LookupError("No confidence calibration policy found")
        return _to_policy_record(fallback_row)

    def upsert_policy(
        self,
        *,
        version: str,
        min_claim_count: int,
        min_total_evidence_pointers: int,
        min_evidence_coverage_rate: float,
        max_evidence_gap_claims: int,
        min_confidence_score: float | None,
        source_audit_run_id: str | None,
        reviewer_outcome_counts: dict[str, int] | None,
        notes: str | None,
        activate: bool = False,
        activated_at: str | None = None,
    ) -> ConfidenceCalibrationPolicyRecord:
        normalized_version = version.strip()
        if not normalized_version:
            raise ValueError("version must be non-empty")

        if min_claim_count < 0:
            raise ValueError("min_claim_count must be >= 0")
        if min_total_evidence_pointers < 0:
            raise ValueError("min_total_evidence_pointers must be >= 0")
        if not 0.0 <= min_evidence_coverage_rate <= 1.0:
            raise ValueError("min_evidence_coverage_rate must be within [0.0, 1.0]")
        if max_evidence_gap_claims < 0:
            raise ValueError("max_evidence_gap_claims must be >= 0")
        if min_confidence_score is not None and not 0.0 <= min_confidence_score <= 1.0:
            raise ValueError("min_confidence_score must be within [0.0, 1.0] when provided")

        if reviewer_outcome_counts is None:
            reviewer_outcome_counts_json = None
        else:
            reviewer_outcome_counts_json = json.dumps(
                reviewer_outcome_counts,
                separators=(",", ":"),
                sort_keys=True,
            )

        with self._connection:
            if activate:
                self._connection.execute(
                    """
                    UPDATE confidence_calibration_policies
                    SET
                        is_active = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE is_active = 1
                    """
                )
            self._connection.execute(
                """
                INSERT INTO confidence_calibration_policies (
                    version,
                    min_claim_count,
                    min_total_evidence_pointers,
                    min_evidence_coverage_rate,
                    max_evidence_gap_claims,
                    min_confidence_score,
                    source_audit_run_id,
                    created_from_reviewer_outcomes_json,
                    notes,
                    is_active,
                    activated_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(version) DO UPDATE SET
                    min_claim_count = excluded.min_claim_count,
                    min_total_evidence_pointers = excluded.min_total_evidence_pointers,
                    min_evidence_coverage_rate = excluded.min_evidence_coverage_rate,
                    max_evidence_gap_claims = excluded.max_evidence_gap_claims,
                    min_confidence_score = excluded.min_confidence_score,
                    source_audit_run_id = excluded.source_audit_run_id,
                    created_from_reviewer_outcomes_json = excluded.created_from_reviewer_outcomes_json,
                    notes = excluded.notes,
                    is_active = excluded.is_active,
                    activated_at = excluded.activated_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    normalized_version,
                    min_claim_count,
                    min_total_evidence_pointers,
                    min_evidence_coverage_rate,
                    max_evidence_gap_claims,
                    min_confidence_score,
                    source_audit_run_id,
                    reviewer_outcome_counts_json,
                    notes,
                    1 if activate else 0,
                    activated_at if activate else None,
                ),
            )

            if activate:
                self._connection.execute(
                    """
                    UPDATE confidence_calibration_policies
                    SET
                        is_active = CASE WHEN version = ? THEN 1 ELSE 0 END,
                        activated_at = CASE
                            WHEN version = ? THEN COALESCE(?, activated_at, CURRENT_TIMESTAMP)
                            ELSE activated_at
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (normalized_version, normalized_version, activated_at),
                )

        return self.get_policy(version=normalized_version)

    def set_active_policy(self, *, version: str, activated_at: str | None = None) -> ConfidenceCalibrationPolicyRecord:
        policy = self.get_policy(version=version)
        with self._connection:
            self._connection.execute(
                """
                UPDATE confidence_calibration_policies
                SET
                    is_active = CASE WHEN version = ? THEN 1 ELSE 0 END,
                    activated_at = CASE
                        WHEN version = ? THEN COALESCE(?, activated_at, CURRENT_TIMESTAMP)
                        ELSE activated_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (policy.version, policy.version, activated_at),
            )

        return self.get_active_policy()

    def get_policy(self, *, version: str) -> ConfidenceCalibrationPolicyRecord:
        row = self._connection.execute(
            """
            SELECT
                version,
                min_claim_count,
                min_total_evidence_pointers,
                min_evidence_coverage_rate,
                max_evidence_gap_claims,
                min_confidence_score,
                source_audit_run_id,
                created_from_reviewer_outcomes_json,
                notes,
                is_active,
                activated_at,
                created_at,
                updated_at
            FROM confidence_calibration_policies
            WHERE version = ?
            """,
            (version,),
        ).fetchone()
        if row is None:
            raise LookupError(f"confidence calibration policy not found: {version}")
        return _to_policy_record(row)


def _to_policy_record(row: sqlite3.Row | tuple[object, ...]) -> ConfidenceCalibrationPolicyRecord:
    values = tuple(cast(tuple[Any, ...], row))
    return ConfidenceCalibrationPolicyRecord(
        version=str(values[0]),
        min_claim_count=int(values[1]),
        min_total_evidence_pointers=int(values[2]),
        min_evidence_coverage_rate=float(values[3]),
        max_evidence_gap_claims=int(values[4]),
        min_confidence_score=float(values[5]) if values[5] is not None else None,
        source_audit_run_id=str(values[6]) if values[6] is not None else None,
        created_from_reviewer_outcomes_json=str(values[7]) if values[7] is not None else None,
        notes=str(values[8]) if values[8] is not None else None,
        is_active=bool(values[9]),
        activated_at=str(values[10]) if values[10] is not None else None,
        created_at=str(values[11]),
        updated_at=str(values[12]),
    )
