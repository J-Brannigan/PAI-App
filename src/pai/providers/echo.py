from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional
import time
from .registry import ProviderRegistry
from ..secrets.sources import SecretsResolver
from ..core.ports import Message

_LOREM_50 = ("Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
             "incididunt ut labore et dolore magna aliqua Curabitur non nulla sit amet nisl "
             "tempor convallis quis ac lectus Phasellus viverra nulla ut metus varius laoreet "
             "Quisque rutrum Aenean imperdiet Etiam ultricies nisi vel augue Curabitur ullamcorper ultricies nisi").split()

@ProviderRegistry.register("echo")
class EchoProvider:
    model = "echo-lorem"

    @classmethod
    def create(cls, *, model_name: str, provider_cfg: Dict[str, Any], secrets: SecretsResolver):
        delay = float(provider_cfg.get("token_delay", 0.125))
        return cls(token_delay=delay)

    def __init__(self, token_delay: float = 0.125):
        self.token_delay = token_delay

    def chat(self, messages: List[Message]) -> Dict[str, str]:
        return {"content": " ".join(_LOREM_50)}

    def chat_stream(self, messages: List[Message]) -> Iterable[str]:
        def gen():
            last = len(_LOREM_50) - 1
            for i, w in enumerate(_LOREM_50):
                yield w + ("" if i == last else " ")
                if self.token_delay > 0: time.sleep(self.token_delay)
        return gen()
