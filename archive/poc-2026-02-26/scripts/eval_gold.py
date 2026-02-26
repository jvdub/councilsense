from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script (sys.path[0] becomes ./scripts). Add repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from minutes_spike.gold import evaluate_gold_suite


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="CouncilSense gold-set regression checker")
    p.add_argument("--gold", type=str, default="gold/gold.yaml", help="Path to gold suite YAML (default: gold/gold.yaml)")
    args = p.parse_args(argv)

    gold_path = Path(args.gold).resolve()
    failures = evaluate_gold_suite(gold_path)

    if failures:
        print(f"Gold check failed: {len(failures)} failure(s)")
        for f in failures:
            print(f"- {f.case_id}: {f.message}")
        return 1

    print("Gold check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
