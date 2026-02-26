from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ProfileError(ValueError):
	pass


DEFAULT_PROFILE_BASENAME = "interest_profile.yaml"


DEFAULT_PROFILE_TEMPLATE = """version: 1
profile_name: "local"

# Simple, explicit rules first. We'll evolve these once we see real minutes format.
rules:
  - id: neighborhood_sunset_flats
    description: "Mentions Sunset Flats (neighborhood)"
    type: keyword_any
    enabled: true
    keywords:
      - "sunset flats"
      - "sunset flat"
    min_hits: 1

  - id: city_code_changes_residential
    description: "City code / ordinance changes, especially residential"
    type: keyword_with_context
    enabled: true
    keywords:
      - "ordinance"
      - "city code"
      - "zoning code"
      - "code amendment"
      - "ordinance amendment"
      - "amendment to"
      - "chapter"
      - "section"
      - "emmc"
    context_keywords:
      - "amend"
      - "amendment"
      - "repeal"
      - "adopt"
      - "adoption"
      - "update"
      - "revise"
      - "modify"
      - "change"
      - "first reading"
      - "second reading"
      - "public hearing"
      - "proposed ordinance"
      - "draft ordinance"
      - "residential"
      - "single-family"
      - "multi-family"
      - "dwelling"
      - "accessory dwelling"
      - "adu"
    window_chars: 400
    min_hits: 1

  - id: laundromat_new_or_approved
    description: "Laundromat mentioned in a build/approval context"
    type: keyword_with_context
    enabled: true
    keywords:
      - "laundromat"
      - "washateria"
      - "coin laundry"
    context_keywords:
      - "conditional use"
      - "special use"
      - "permit"
      - "approval"
      - "approve"
      - "application"
      - "site plan"
      - "development"
      - "build"
      - "construct"
      - "proposed"
      - "rezoning"
      - "zoning"
      - "public hearing"
    window_chars: 300
    min_hits: 1

output:
  evidence:
    snippet_chars: 260
    max_snippets_per_rule: 5
"""


def _xdg_config_home() -> Path:
	base = os.environ.get("XDG_CONFIG_HOME")
	if base:
		return Path(base)
	home = os.environ.get("HOME")
	if home:
		return Path(home) / ".config"
	return Path.home() / ".config"


def default_profile_path() -> Path:
	return _xdg_config_home() / "councilsense" / DEFAULT_PROFILE_BASENAME


def resolve_profile_path(explicit: Optional[str], *, prefer_xdg: bool = False) -> Path:
	"""Resolve the interest profile path.

	Precedence:
	1) explicit CLI arg
	2) COUNCILSENSE_PROFILE env var
	3) XDG config file (if exists)
	4) local ./interest_profile.yaml (if exists)
	5) XDG config file (default location)

	This supports a single stable local profile while keeping
	backwards-compatible behavior for repo-local usage.
	"""

	if explicit:
		return Path(explicit)

	env_path = os.environ.get("COUNCILSENSE_PROFILE")
	if env_path:
		return Path(env_path)

	xdg = default_profile_path()
	if xdg.exists():
		return xdg

	if not prefer_xdg:
		local = Path.cwd() / DEFAULT_PROFILE_BASENAME
		if local.exists():
			return local

	return xdg


def init_profile(path: Path, *, overwrite: bool = False) -> Path:
	"""Create a starter profile file.

	If overwrite is False and the path exists, this is a no-op.
	Returns the path.
	"""

	if path.exists() and not overwrite:
		return path

	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(DEFAULT_PROFILE_TEMPLATE, encoding="utf-8")
	return path


def load_profile(path: Path) -> Dict[str, Any]:
	try:
		with path.open("r", encoding="utf-8") as f:
			data = yaml.safe_load(f) or {}
	except FileNotFoundError as e:
		raise ProfileError(
			f"Interest profile not found: {path}. "
			"Create one with: --init-profile"
		) from e
	except Exception as e:
		raise ProfileError(f"Failed to read interest profile YAML: {path}") from e

	if not isinstance(data, dict):
		raise ProfileError("Interest profile YAML must be a mapping (top-level object).")

	validate_profile(data)
	return data


def _as_str_list(value: Any) -> List[str]:
	if value is None:
		return []
	if not isinstance(value, list):
		return []
	out: List[str] = []
	for item in value:
		if isinstance(item, str) and item.strip():
			out.append(item)
	return out


def validate_profile(profile: Dict[str, Any]) -> None:
	"""Lightweight validation for user-edited profiles."""

	llm = profile.get("llm")
	if llm is not None:
		if not isinstance(llm, dict):
			raise ProfileError("Profile field 'llm' must be an object.")

		provider = llm.get("provider")
		if provider is not None and (not isinstance(provider, str) or not provider.strip()):
			raise ProfileError("Profile field 'llm.provider' must be a non-empty string if provided.")

		endpoint = llm.get("endpoint")
		if endpoint is not None and (not isinstance(endpoint, str) or not endpoint.strip()):
			raise ProfileError("Profile field 'llm.endpoint' must be a non-empty string if provided.")

		model = llm.get("model")
		if model is not None and (not isinstance(model, str) or not model.strip()):
			raise ProfileError("Profile field 'llm.model' must be a non-empty string if provided.")

		timeout_s = llm.get("timeout_s")
		if timeout_s is not None:
			try:
				float(timeout_s)
			except Exception as e:
				raise ProfileError("Profile field 'llm.timeout_s' must be a number.") from e

	rules = profile.get("rules")
	if rules is None:
		return
	if not isinstance(rules, list):
		raise ProfileError("Profile field 'rules' must be a list.")

	for idx, rule in enumerate(rules):
		if not isinstance(rule, dict):
			raise ProfileError(f"Rule #{idx + 1} must be a mapping/object.")

		rid = rule.get("id")
		if not isinstance(rid, str) or not rid.strip():
			raise ProfileError(f"Rule #{idx + 1} is missing a non-empty 'id'.")

		rtype = rule.get("type")
		if rtype not in ("keyword_any", "keyword_with_context"):
			raise ProfileError(
				f"Rule '{rid}' has unsupported type '{rtype}'. "
				"Supported: keyword_any, keyword_with_context."
			)

		keywords = _as_str_list(rule.get("keywords"))
		if not keywords:
			raise ProfileError(f"Rule '{rid}' must have a non-empty 'keywords' list.")

		if rtype == "keyword_with_context":
			ctx = _as_str_list(rule.get("context_keywords"))
			if not ctx:
				raise ProfileError(
					f"Rule '{rid}' is keyword_with_context but has no 'context_keywords'."
				)

		for field in ("min_hits", "window_chars"):
			if field in rule and rule[field] is not None:
				try:
					int(rule[field])
				except Exception as e:
					raise ProfileError(
						f"Rule '{rid}' field '{field}' must be an integer."
					) from e

	evidence = ((profile.get("output") or {}).get("evidence") or {})
	if evidence and not isinstance(evidence, dict):
		raise ProfileError("Profile field 'output.evidence' must be an object.")

	for field in ("snippet_chars", "max_snippets_per_rule"):
		if field in evidence and evidence[field] is not None:
			try:
				int(evidence[field])
			except Exception as e:
				raise ProfileError(
					f"Profile field 'output.evidence.{field}' must be an integer."
				) from e