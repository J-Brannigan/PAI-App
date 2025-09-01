# tests/test_chat_session.py

from __future__ import annotations
import sys
from pathlib import Path

# Ensure "src" is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pai.core.chat_session import ChatSession
from pai.storage.transcript import Transcript


class FakeProvider:
    def __init__(self, text="hello"):
        self.model = "fake"
        self.text = text

    def chat(self, _messages):
        return {"content": self.text}

    def chat_stream(self, _messages):
        # yield in two chunks to simulate streaming
        mid = len(self.text) // 2
        yield self.text[:mid]
        yield self.text[mid:]


def test_run_turn_non_stream():
    t = Transcript(system_prompt="sys", root_dir=None)
    cs = ChatSession(model=FakeProvider("pong"), transcript=t)

    out = cs.run_turn("ping")
    assert out == "pong"

    # provider-ready history: system, user, assistant
    msgs = t.messages
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "ping"}
    assert msgs[2] == {"role": "assistant", "content": "pong"}


def test_run_turn_stream_persists_final():
    t = Transcript(system_prompt="sys", root_dir=None)
    cs = ChatSession(model=FakeProvider("stream"), transcript=t)

    gen = cs.run_turn_stream("go")
    chunks = list(gen)
    assert "".join(chunks) == "stream"

    # assistant final message persisted
    assert t.messages[-1] == {"role": "assistant", "content": "stream"}


def test_run_turn_stream_partial_on_close():
    # Simulate user interrupt after first chunk
    class SlowProvider(FakeProvider):
        def chat_stream(self, _messages):
            yield "par"
            # caller will close() before we yield more

    t = Transcript(system_prompt="sys", root_dir=None)
    cs = ChatSession(model=SlowProvider("partial"), transcript=t)

    gen = cs.run_turn_stream("go")
    first = next(gen)
    assert first == "par"
    # close the generator -> ChatSession should persist partial "par"
    gen.close()

    assert t.messages[-1] == {"role": "assistant", "content": "par"}
