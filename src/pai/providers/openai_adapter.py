# src/pai/providers/openai_adapter.py
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

from openai import OpenAI

from pai.providers.registry import ProviderRegistry
from pai.core.errors import ProviderClientError, ProviderTransientError


def _classify_openai_exception(exc: Exception) -> Exception:
    """
    Convert OpenAI/client exceptions into neutral provider errors.
    Avoid hard dependency on specific SDK exception classes by inspecting attributes/message.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    msg = str(exc)

    if status is not None:
        s = int(status)
        if s == 429 or 500 <= s <= 599:
            return ProviderTransientError(msg)
        if 400 <= s < 500:
            return ProviderClientError(msg)
        # Unknown status → be conservative
        return ProviderTransientError(msg) if s >= 500 else ProviderClientError(msg)

    lower = msg.lower()
    if any(k in lower for k in ("rate limit", "temporarily unavailable", "timeout", "timed out")):
        return ProviderTransientError(msg)
    if any(k in lower for k in ("invalid_request_error", "unsupported", "parameter", "authentication")):
        return ProviderClientError(msg)
    return ProviderTransientError(msg)


@ProviderRegistry.register("openai")
class OpenAIAdapter:
    """
    Thin adapter:
    - expects 'params' in provider_cfg to be pre-filtered by bootstrap/param policy
    - maps SDK errors to neutral ProviderClientError / ProviderTransientError
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
    ):
        self.model = model
        # Allow optional base_url/organization passthrough if you use them
        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        if organization:
            client_kwargs["organization"] = organization
        self.client = OpenAI(**client_kwargs)

        self.params = params or {}
        self.timeout = timeout

    @classmethod
    def create(cls, *, model_name: str, provider_cfg: Dict[str, Any], secrets) -> "OpenAIAdapter":
        api_key = secrets.secret("openai", "api_key")
        if not api_key:
            raise ProviderClientError("No API key for 'openai'")

        # These should already be filtered by your YAML policy in bootstrap
        params = (provider_cfg or {}).get("params") or {}
        timeout = (provider_cfg or {}).get("timeout")
        base_url = (provider_cfg or {}).get("base_url")
        organization = (provider_cfg or {}).get("organization")

        return cls(
            model=model_name,
            api_key=api_key,
            params=params,
            timeout=timeout,
            base_url=base_url,
            organization=organization,
        )

    def _build_args(self, messages: List[Dict[str, Any]], *, stream: bool) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            **self.params,  # already effective (pre-filtered) params
        }
        if self.timeout is not None:
            args["timeout"] = self.timeout
        return args

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, str]:
        try:
            resp = self.client.chat.completions.create(**self._build_args(messages, stream=False))
            msg = resp.choices[0].message
            return {"content": msg.content or ""}
        except Exception as e:
            raise _classify_openai_exception(e)

    def chat_stream(self, messages: List[Dict[str, Any]]) -> Iterable[str]:
        try:
            stream = self.client.chat.completions.create(**self._build_args(messages, stream=True))
        except Exception as e:
            raise _classify_openai_exception(e)

        for chunk in stream:
            piece = None
            try:
                piece = chunk.choices[0].delta.content
            except Exception:
                piece = None
            if piece:
                yield piece
