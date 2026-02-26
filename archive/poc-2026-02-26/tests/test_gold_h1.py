from __future__ import annotations

from pathlib import Path

from minutes_spike.gold import evaluate_gold_suite


def test_gold_suite_runs_clean() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gold_path = repo_root / "gold" / "gold.yaml"
    failures = evaluate_gold_suite(gold_path)
    assert failures == []
