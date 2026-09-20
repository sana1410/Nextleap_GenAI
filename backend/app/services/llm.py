"""Thin OpenAI-compatible chat client (Groq by default). The API key never leaves the server."""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from app.config import Settings


class LLMError(Exception):
    pass


class LLMRateLimitError(LLMError):
    """The provider returned HTTP 429. Never retried in the request path."""

    def __init__(self, message: str, retry_after: Optional[float] = None, headers: Optional[Dict[str, str]] = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.headers = headers or {}


@dataclass
class LLMResponse:
    content: str
    total_tokens: Optional[int] = None
    headers: Dict[str, str] = field(default_factory=dict)


def _rate_limit_headers(response: httpx.Response) -> Dict[str, str]:
    return {k.lower(): v for k, v in response.headers.items() if k.lower().startswith(("x-ratelimit", "retry-after"))}


def _seconds(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class LLMClient:
    def __init__(self, settings: Settings, transport: Optional[httpx.BaseTransport] = None):
        self._settings = settings
        self._transport = transport

    def _payload(self, system: str, user: str) -> Dict[str, Any]:
        s = self._settings
        payload: Dict[str, Any] = {
            "model": s.llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": s.llm_temperature,
            "max_completion_tokens": s.llm_max_completion_tokens,
            "response_format": {"type": "json_object"},
        }
        if s.llm_reasoning_effort:
            payload["reasoning_effort"] = s.llm_reasoning_effort
        return payload

    def complete(self, system: str, user: str) -> LLMResponse:
        s = self._settings
        url = "{}/chat/completions".format(s.llm_base_url.rstrip("/"))
        headers = {"Authorization": "Bearer {}".format(s.llm_api_key)}
        try:
            with httpx.Client(timeout=s.llm_timeout_seconds, transport=self._transport) as client:
                response = client.post(url, json=self._payload(system, user), headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError("LLM request failed: {}".format(type(exc).__name__)) from exc

        rl_headers = _rate_limit_headers(response)
        if response.status_code == 429:
            raise LLMRateLimitError("LLM rate limited (HTTP 429)", _seconds(rl_headers.get("retry-after")), rl_headers)
        if response.status_code >= 400:
            raise LLMError("LLM returned HTTP {}".format(response.status_code))
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected LLM response shape") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM returned empty content")

        usage = body.get("usage") if isinstance(body, dict) else None
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        return LLMResponse(
            content=content,
            total_tokens=total if isinstance(total, int) and not isinstance(total, bool) else None,
            headers=rl_headers,
        )
