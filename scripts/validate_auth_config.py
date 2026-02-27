#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

EXPECTED_ENABLED_PROVIDERS = {"google"}
REQUIRED_ENVIRONMENTS = ("local", "dev")
ENV_WIRING = {
    "local": {
        "callback": "AUTH_CALLBACK_URL_LOCAL",
        "logout": "AUTH_LOGOUT_URL_LOCAL",
    },
    "dev": {
        "callback": "AUTH_CALLBACK_URL_DEV",
        "logout": "AUTH_LOGOUT_URL_DEV",
    },
}


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_provider_config(config: dict) -> list[str]:
    errors: list[str] = []
    enabled = set(config.get("social_providers", {}).get("enabled", []))

    if enabled != EXPECTED_ENABLED_PROVIDERS:
        errors.append(
            "social_providers.enabled must be exactly ['google']"
        )

    return errors


def _validate_environment_urls(config: dict) -> list[str]:
    errors: list[str] = []
    environments = config.get("environments", {})

    for env_name in REQUIRED_ENVIRONMENTS:
        env_config = environments.get(env_name)
        if not env_config:
            errors.append(f"missing environments.{env_name} config")
            continue

        callback_urls = env_config.get("callback_urls", [])
        logout_urls = env_config.get("logout_urls", [])

        if not callback_urls:
            errors.append(f"environments.{env_name}.callback_urls must not be empty")
        if not logout_urls:
            errors.append(f"environments.{env_name}.logout_urls must not be empty")

        expected_callback = os.getenv(ENV_WIRING[env_name]["callback"])
        expected_logout = os.getenv(ENV_WIRING[env_name]["logout"])

        if expected_callback and expected_callback not in callback_urls:
            errors.append(
                f"environments.{env_name}.callback_urls missing env-wired value: {expected_callback}"
            )
        if expected_logout and expected_logout not in logout_urls:
            errors.append(
                f"environments.{env_name}.logout_urls missing env-wired value: {expected_logout}"
            )

    return errors


def _validate_required_env_vars() -> list[str]:
    errors: list[str] = []
    for env_name, keys in ENV_WIRING.items():
        for key in keys.values():
            if not os.getenv(key):
                errors.append(
                    f"missing required env var for {env_name} auth wiring: {key}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Google-only managed auth config and callback/logout URL wiring"
    )
    parser.add_argument(
        "--config",
        default="config/auth/managed_auth.json",
        help="Path to managed auth configuration JSON",
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="Skip required environment-variable validation",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}")
        return 1

    config = _load_json(config_path)
    errors = []
    errors.extend(_validate_provider_config(config))
    errors.extend(_validate_environment_urls(config))

    if not args.skip_env_check:
        errors.extend(_validate_required_env_vars())

    if errors:
        print("Auth config validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Auth config validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
