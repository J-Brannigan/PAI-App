from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional
import time

_LOREM_50 = (
    "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua Curabitur non nulla sit amet nisl "
    "tempor convallis quis ac lectus Phasellus viverra nulla ut metus varius laoreet "
    "Quisque rutrum Aenean imperdiet Etiam ultricies nisi vel augue Curabitur ullamcorper ultricies nisi"
).split()

class EchoProvider:
    """
    Offline stub that returns a fixed 50-word lorem ipsum.
    Streaming yields one word at a time with a small delay to simulate tokens.
    """
    model = "echo-lorem"

    def __init__(self, token_delay: float = 0.125, words: Optional[List[str]] = None):
        self.token_delay = float(token_delay)
        self.words = list(words) if words is not None else list(_LOREM_50)

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, str]:
        return {"content": " ".join(self.words)}

    def chat_stream(self, messages: List[Dict[str, Any]]) -> Iterable[str]:
        def gen():
            try:
                last_idx = len(self.words) - 1
                for i, w in enumerate(self.words):
                    yield w + ("" if i == last_idx else " ")
                    if self.token_delay > 0:
                        time.sleep(self.token_delay)
            except KeyboardInterrupt:
                raise
        return gen()
