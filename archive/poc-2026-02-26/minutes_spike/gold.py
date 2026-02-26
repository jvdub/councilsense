from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from . import cli


@dataclass(frozen=True)
class GoldFailure:
    case_id: str
    message: str


def _as_path(base: Path, raw: Any) -> Optional[Path]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    p = Path(raw)
    return (base / p).resolve() if not p.is_absolute() else p


def load_gold_file(gold_path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Gold file must be a mapping: {gold_path}")
    return data


def _snippet_contains_all(snippet: str, needles: List[str]) -> bool:
    s = (snippet or "").casefold()
    return all(n.casefold() in s for n in needles if isinstance(n, str) and n)


def _highlight_matches_expectation(highlight: Dict[str, Any], needles: List[str]) -> bool:
    evidence = highlight.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        snip = ev.get("snippet")
        if isinstance(snip, str) and _snippet_contains_all(snip, needles):
            return True
    return False


def evaluate_gold_case(
    *,
    case: Dict[str, Any],
    base_dir: Path,
    profile_path: Path,
) -> Tuple[int, Dict[str, Any]]:
    case_id = str(case.get("id") or "")
    meeting_id = str(case.get("meeting_id") or case_id or "gold")

    text_path = _as_path(base_dir, case.get("text"))
    pdf_path = _as_path(base_dir, case.get("pdf"))

    if text_path is None and pdf_path is None:
        raise ValueError(f"Gold case {case_id!r} must specify text or pdf")

    with tempfile.TemporaryDirectory(prefix="councilsense-gold-") as td:
        out_path = Path(td) / f"{meeting_id}.json"
        argv: List[str] = ["--meeting-id", meeting_id, "--profile", str(profile_path), "--classify-relevance", "--out", str(out_path)]
        if text_path is not None:
            argv.extend(["--text", str(text_path)])
        if pdf_path is not None:
            argv.extend(["--pdf", str(pdf_path)])

        rc = cli.main(argv)
        payload = json.loads(out_path.read_text(encoding="utf-8"))

    return rc, payload


def check_gold_payload(*, case_id: str, payload: Dict[str, Any], expected: List[Dict[str, Any]]) -> List[GoldFailure]:
    failures: List[GoldFailure] = []

    highlights = payload.get("things_you_care_about")
    if not isinstance(highlights, list):
        highlights = []

    for exp in expected:
        if not isinstance(exp, dict):
            continue
        category = exp.get("category")
        if not isinstance(category, str) or not category:
            continue
        needles = exp.get("must_include")
        if not isinstance(needles, list):
            needles = []

        must_link = exp.get("must_link")
        if not isinstance(must_link, str) or must_link not in ("agenda_item", "attachment"):
            must_link = None

        matches = [h for h in highlights if isinstance(h, dict) and (h.get("category") == category or h.get("rule_id") == category)]
        if not matches:
            failures.append(GoldFailure(case_id=case_id, message=f"Missing highlight for category {category}"))
            continue

        if must_link:
            def has_link_bucket(h: Dict[str, Any]) -> bool:
                links = h.get("links")
                if not isinstance(links, dict):
                    return False
                return bool(links.get(must_link))

            if not any(has_link_bucket(h) for h in matches):
                failures.append(
                    GoldFailure(
                        case_id=case_id,
                        message=f"Highlight {category} missing required links.{must_link} pointer",
                    )
                )

        min_count = exp.get("min_count")
        if isinstance(min_count, int) and min_count > 0 and len(matches) < min_count:
            failures.append(
                GoldFailure(case_id=case_id, message=f"Expected at least {min_count} highlights for {category}, got {len(matches)}")
            )

        if needles:
            ok = any(_highlight_matches_expectation(h, needles) for h in matches)
            if not ok:
                failures.append(
                    GoldFailure(
                        case_id=case_id,
                        message=f"Highlight {category} missing required evidence substrings: {needles}",
                    )
                )

    return failures


def evaluate_gold_suite(gold_path: Path) -> List[GoldFailure]:
    gold = load_gold_file(gold_path)

    base_dir = gold_path.parent

    profile_raw = gold.get("profile")
    profile_path = _as_path(base_dir, profile_raw)
    if profile_path is None:
        raise ValueError("Gold file must specify a profile path")

    cases = gold.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Gold file must include non-empty cases[]")

    failures: List[GoldFailure] = []

    for c in cases:
        if not isinstance(c, dict):
            continue
        case_id = str(c.get("id") or "")
        expected = c.get("expected")
        if not isinstance(expected, list):
            expected = []

        rc, payload = evaluate_gold_case(case=c, base_dir=base_dir, profile_path=profile_path)
        if rc != 0:
            failures.append(GoldFailure(case_id=case_id or "(unknown)", message=f"CLI returned non-zero exit code: {rc}"))

        failures.extend(check_gold_payload(case_id=case_id or "(unknown)", payload=payload, expected=expected))

    return failures
