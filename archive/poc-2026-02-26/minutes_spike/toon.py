from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import yaml


class ToonError(ValueError):
    pass


class ToonDecodeError(ToonError):
    pass


@dataclass(frozen=True)
class ToonRoundTrip:
    input_json: Dict[str, Any]
    input_toon: str
    output_toon: str
    output_json: Dict[str, Any]


def encode_json_to_toon(data: Dict[str, Any]) -> str:
    """Encode canonical JSON context to a TOON-ish YAML text.

    This is intentionally conservative: stable keys, stable ordering, and a
    human-readable representation that is LLM-friendly.
    """

    if not isinstance(data, dict):
        raise ToonError("encode_json_to_toon expects a dict")

    # Use YAML as a pragmatic TOON-ish interchange for now.
    # Keep flow style off for readability.
    return yaml.safe_dump(data, sort_keys=True, allow_unicode=True)


def _require_dict(obj: Any, *, where: str) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ToonDecodeError(f"Expected object at {where}.")
    return obj


def _require_str_list(obj: Any, *, where: str) -> List[str]:
    if not isinstance(obj, list):
        raise ToonDecodeError(f"Expected list at {where}.")
    out: List[str] = []
    for idx, item in enumerate(obj):
        if not isinstance(item, str) or not item.strip():
            raise ToonDecodeError(f"Expected non-empty string at {where}[{idx}].")
        out.append(item.strip())
    return out


def decode_toon_to_json(toon_text: str) -> Dict[str, Any]:
    """Decode TOON-ish YAML output to canonical JSON.

    Strict mode (fail fast): unknown structure is rejected.
    Minimum supported schema:

    summary:
      - "..."
      - "..."

    Optional fields (accepted if present): actions, entities, key_terms, citations.
    """

    try:
        parsed = yaml.safe_load(toon_text) or {}
    except Exception as e:
        raise ToonDecodeError("Failed to parse TOON output as YAML.") from e

    data = _require_dict(parsed, where="$")

    allowed_keys = {"summary", "actions", "entities", "key_terms", "citations"}
    unknown = set(data.keys()) - allowed_keys
    if unknown:
        raise ToonDecodeError(f"Unexpected field(s) in TOON output: {sorted(unknown)}")

    if "summary" not in data:
        raise ToonDecodeError("Missing required field: summary")

    out: Dict[str, Any] = {
        "summary": _require_str_list(data.get("summary"), where="summary"),
    }

    # Optional list-of-strings fields
    for k in ("actions", "entities", "key_terms", "citations"):
        if k in data and data[k] is not None:
            out[k] = _require_str_list(data[k], where=k)

    return out
