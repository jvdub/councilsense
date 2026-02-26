from __future__ import annotations

import json
import re
import socket
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .prompts import build_summarize_agenda_item_bullets_prompt


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    endpoint: str
    model: str
    timeout_s: float = 120.0


@dataclass(frozen=True)
class SummaryResult:
    bullets: list[str]
    raw_text: str


@dataclass(frozen=True)
class LLMError(Exception):
    code: str
    message: str
    retryable: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:  # pragma: no cover
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.provider:
            out["provider"] = self.provider
        if self.model:
            out["model"] = self.model
        if self.details:
            out["details"] = self.details
        return out


class LLMProvider:
    def generate_text(self, *, prompt: str) -> str:
        raise NotImplementedError

    def summarize_agenda_item(self, *, title: str, body_text: str) -> SummaryResult:
        raise NotImplementedError


def _normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if endpoint.endswith("/"):
        endpoint = endpoint[:-1]
    return endpoint


_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]|\d+\.|\d+\))\s+")


def _to_bullets(text: str, *, max_bullets: int = 12) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines()]
    bullets: list[str] = []
    for ln in lines:
        if not ln:
            continue
        ln = _BULLET_PREFIX_RE.sub("", ln).strip()
        if not ln:
            continue
        bullets.append(ln)
        if len(bullets) >= max_bullets:
            break

    if bullets:
        return bullets

    # Fallback: if the model returned a paragraph, return it as a single bullet.
    compact = re.sub(r"\s+", " ", text).strip()
    return [compact] if compact else []


class OllamaProvider(LLMProvider):
    def __init__(self, cfg: ProviderConfig):
        if not cfg.model.strip():
            raise ValueError("cfg.model is required")
        self._cfg = ProviderConfig(
            provider=cfg.provider,
            endpoint=_normalize_endpoint(cfg.endpoint),
            model=cfg.model.strip(),
            timeout_s=float(cfg.timeout_s),
        )

    def generate_text(self, *, prompt: str) -> str:
        url = urljoin(self._cfg.endpoint + "/", "api/generate")
        payload = {
            "model": self._cfg.model,
            "prompt": prompt,
            "stream": False,
        }
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=self._cfg.timeout_s) as resp:
                raw_bytes = resp.read()
        except HTTPError as e:
            body = None
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = None

            details: Dict[str, Any] = {
                "http_status": getattr(e, "code", None),
            }
            if body:
                details["body_preview"] = body[:500]
                try:
                    j = json.loads(body)
                    if isinstance(j, dict) and isinstance(j.get("error"), str):
                        err = j["error"].strip()
                        if "model" in err.lower() and ("not found" in err.lower() or "pull" in err.lower()):
                            raise LLMError(
                                code="llm_model_missing",
                                message=f"Ollama model not available: {self._cfg.model}. {err}",
                                retryable=False,
                                provider=self._cfg.provider,
                                model=self._cfg.model,
                                details=details,
                            )
                except json.JSONDecodeError:
                    pass

            raise LLMError(
                code="llm_http_error",
                message=f"Ollama request failed (HTTP {getattr(e, 'code', 'unknown')}).",
                retryable=False,
                provider=self._cfg.provider,
                model=self._cfg.model,
                details=details,
            )
        except (URLError, ConnectionError) as e:
            raise LLMError(
                code="llm_unavailable",
                message=f"Ollama is unreachable at {self._cfg.endpoint}. Is it running?",
                retryable=True,
                provider=self._cfg.provider,
                model=self._cfg.model,
                details={"exception_type": type(e).__name__},
            )
        except socket.timeout as e:
            raise LLMError(
                code="llm_timeout",
                message=f"Ollama request timed out after {self._cfg.timeout_s:.0f}s.",
                retryable=True,
                provider=self._cfg.provider,
                model=self._cfg.model,
                details={"exception_type": type(e).__name__},
            )

        try:
            raw = raw_bytes.decode("utf-8", errors="replace")
            data = json.loads(raw)
        except Exception as e:
            raise LLMError(
                code="llm_parse_error",
                message="Failed to parse Ollama response JSON.",
                retryable=False,
                provider=self._cfg.provider,
                model=self._cfg.model,
                details={"exception_type": type(e).__name__},
            )

        if isinstance(data, dict) and isinstance(data.get("error"), str) and data["error"].strip():
            err = data["error"].strip()
            if "model" in err.lower() and ("not found" in err.lower() or "pull" in err.lower()):
                raise LLMError(
                    code="llm_model_missing",
                    message=f"Ollama model not available: {self._cfg.model}. {err}",
                    retryable=False,
                    provider=self._cfg.provider,
                    model=self._cfg.model,
                )
            raise LLMError(
                code="llm_provider_error",
                message=f"Ollama error: {err}",
                retryable=False,
                provider=self._cfg.provider,
                model=self._cfg.model,
            )

        response_text = None
        if isinstance(data, dict):
            response_text = data.get("response")

        if not isinstance(response_text, str):
            raise LLMError(
                code="llm_parse_error",
                message="Ollama response did not include a 'response' string.",
                retryable=False,
                provider=self._cfg.provider,
                model=self._cfg.model,
            )

        return response_text

    def summarize_agenda_item(self, *, title: str, body_text: str) -> SummaryResult:
        prompt = build_summarize_agenda_item_bullets_prompt(title=title, body_text=body_text)

        response_text = self.generate_text(prompt=prompt)
        bullets = _to_bullets(response_text)
        return SummaryResult(bullets=bullets, raw_text=response_text)


def create_llm_provider(cfg: ProviderConfig) -> LLMProvider:
    provider = (cfg.provider or "").strip().lower()
    if provider in ("ollama", ""):
        return OllamaProvider(cfg)
    raise ValueError(f"Unsupported LLM provider: {cfg.provider}")
