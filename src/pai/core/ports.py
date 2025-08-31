from __future__ import annotations
from typing import Protocol, Iterable, List, Dict, Any

class Provider(Protocol):
    """
    Interface the core uses to talk to any LLM backend.
    """

    # Optional: surface the model name for logging/headers
    model: str

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Synchronous call. Returns {'content': <assistant_text>}.
        'messages' should be OpenAI-style: [{'role': 'system'|'user'|'assistant', 'content': '...'}, ...]
        """
        ...

    def chat_stream(self, messages: List[Dict[str, Any]]) -> Iterable[str]:
        """
        Streaming call. Yields text chunks as they arrive.
        """
        ...
