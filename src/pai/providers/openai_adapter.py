from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional
from openai import OpenAI

_ALLOWED_PARAMS = {
    "temperature",
    "top_p",
    "max_tokens",
    "presence_penalty",
    "frequency_penalty",
    "seed",
}

class OpenAIAdapter:
    """
    Thin adapter around the OpenAI SDK that matches the Provider port.
    It does not do retries or fancy error handling — keep that in a separate wrapper if needed.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        request_timeout: Optional[float] = 60,
    ):
        self.model = model
        self._params = {k: v for k, v in (params or {}).items() if k in _ALLOWED_PARAMS and v is not None}
        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        if organization:
            client_kwargs["organization"] = organization
        self._client = OpenAI(**client_kwargs)
        self._timeout = request_timeout

    def _common_args(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **self._params,
        }
        if self._timeout is not None:
            args["timeout"] = self._timeout
        return args

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, str]:
        resp = self._client.chat.completions.create(**self._common_args(messages))
        msg = resp.choices[0].message
        return {"content": (msg.content or "")}

    def chat_stream(self, messages: List[Dict[str, Any]]) -> Iterable[str]:
        args = self._common_args(messages)
        args["stream"] = True
        stream = self._client.chat.completions.create(**args)
        for chunk in stream:
            # Defensive across minor SDK deltas
            try:
                piece = chunk.choices[0].delta.content
            except Exception:
                piece = None
            if piece:
                yield piece
