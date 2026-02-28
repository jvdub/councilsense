from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from councilsense.db import OperatorViewRepository


def build_operator_triage_view(
    *,
    connection: sqlite3.Connection,
    stale_before: str,
    manual_review_limit: int = 100,
    generated_at: str | None = None,
) -> dict[str, Any]:
    repository = OperatorViewRepository(connection)
    emitted_at = generated_at or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    stale_sources = tuple(asdict(record) for record in repository.list_stale_sources(stale_before=stale_before))
    failing_sources = tuple(asdict(record) for record in repository.list_failing_sources())
    manual_review_runs = tuple(
        asdict(record)
        for record in repository.list_manual_review_needed_runs(limit=manual_review_limit)
    )

    return {
        "generated_at": emitted_at,
        "stale_before": stale_before,
        "stale_sources": stale_sources,
        "failing_sources": failing_sources,
        "manual_review_runs": manual_review_runs,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Operator triage view for stale/failing sources and manual review runs")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument(
        "--stale-before",
        required=True,
        help="Timestamp cutoff for stale sources (TEXT comparison in SQLite)",
    )
    parser.add_argument(
        "--manual-review-limit",
        type=int,
        default=100,
        help="Maximum number of manual-review-needed runs to include",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    db_path = Path(args.db)

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        payload = build_operator_triage_view(
            connection=connection,
            stale_before=args.stale_before,
            manual_review_limit=args.manual_review_limit,
        )
    finally:
        connection.close()

    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
