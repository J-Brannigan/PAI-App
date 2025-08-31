from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional
from openai import OpenAI

from .registry import ProviderRegistry
from ..secrets.sources import SecretsResolver

_ALLOWED_PARAMS = {"temperature","top_p","max_tokens","presence_penalty","frequency_penalty","seed"}

@ProviderRegistry.register("openai")
class OpenAIAdapter:
    model: str

    def __init__(self, model: str, api_key: str, *, params: Optional[Dict[str, Any]] = None,
                 base_url: Optional[str] = None, organization: Optional[str] = None,
                 request_timeout: Optional[float] = 60):
        self.model = model
        self._params = {k: v for k, v in (params or {}).items() if k in _ALLOWED_PARAMS and v is not None}
        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url: client_kwargs["base_url"] = base_url
        if organization: client_kwargs["organization"] = organization
        self._client = OpenAI(**client_kwargs)
        self._timeout = request_timeout

    # --- required factory for registry bootstrap ---
    @classmethod
    def create(cls, *, model_name: str, provider_cfg: Dict[str, Any], secrets: SecretsResolver):
        api_key = secrets.secret("openai", "api_key")
        if not api_key:
            raise RuntimeError("No API key for 'openai'. Check secrets.order/mapping in config.")
        return cls(
            model=model_name,
            api_key=api_key,
            params=provider_cfg.get("params"),
            base_url=provider_cfg.get("base_url"),
            organization=provider_cfg.get("organization"),
            request_timeout=provider_cfg.get("timeout", 60),
        )

    def _common_args(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        args: Dict[str, Any] = {"model": self.model, "messages": messages, **self._params}
        if self._timeout is not None:
            args["timeout"] = self._timeout
        return args

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, str]:
        resp = self._client.chat.completions.create(**self._common_args(messages))
        msg = resp.choices[0].message
        return {"content": (msg.content or "")}

    def chat_stream(self, messages: List[Dict[str, Any]]) -> Iterable[str]:
        args = self._common_args(messages); args["stream"] = True
        stream = self._client.chat.completions.create(**args)
        for chunk in stream:
            try:
                piece = chunk.choices[0].delta.content
            except Exception:
                piece = None
            if piece:
                yield piece
