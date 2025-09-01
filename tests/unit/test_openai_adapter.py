# tests/test_openai_adapter.py

from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List
import types

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Import the module, then monkeypatch its OpenAI class
import pai.providers.openai_adapter as oa  # type: ignore


# -------- Fakes to replace the OpenAI SDK --------

class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content

class _FakeChoiceMsg:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)

class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoiceMsg(content)]

class _FakeDelta:
    def __init__(self, content: str) -> None:
        self.content = content

class _FakeChoiceDelta:
    def __init__(self, content: str) -> None:
        self.delta = _FakeDelta(content)

class _FakeChunk:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoiceDelta(content)]

class _FakeCompletions:
    def __init__(self, parent) -> None:
        self.parent = parent
    def create(self, **kwargs):
        # streaming path
        if kwargs.get("stream"):
            parts = ["he", "llo"]
            def _iter():
                for p in parts:
                    yield _FakeChunk(p)
            return _iter()
        # non-streaming path
        return _FakeResponse("hello world")

class _FakeChat:
    def __init__(self, parent) -> None:
        self.parent = parent
        self.completions = _FakeCompletions(parent)

class _FakeOpenAI:
    def __init__(self, **_kwargs) -> None:
        self.chat = _FakeChat(self)


def test_openai_adapter_chat_and_stream(monkeypatch):
    # Replace OpenAI in the adapter module with our fake
    monkeypatch.setattr(oa, "OpenAI", _FakeOpenAI, raising=True)

    adapter = oa.OpenAIAdapter(model="test-model", api_key="sk-test")

    # Non-stream call
    out = adapter.chat([{"role": "user", "content": "hi"}])
    assert out == {"content": "hello world"}

    # Stream call (yields two chunks)
    chunks = list(adapter.chat_stream([{"role": "user", "content": "hi"}]))
    assert chunks == ["he", "llo"]
    # Adapter exposes model attribute
    assert adapter.model == "test-model"
