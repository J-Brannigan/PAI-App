# tests/unit/test_resilient_provider.py

from __future__ import annotations
import sys
from pathlib import Path
import pytest

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pai.resilience.resilient_provider import ResilientProvider, ResiliencePolicy


# -------- helpers --------

class FlakyThenOK:
    def __init__(self, fail_times=2, stream=False):
        self.calls = 0
        self.fail_times = fail_times
        self.stream = stream
        self.model = "flaky"

    def chat(self, _):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TimeoutError("boom")
        return {"content": "ok"}

    def chat_stream(self, _):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TimeoutError("boom")
        yield "ok"


class MidStreamBoom:
    model = "mid"

    def chat(self, _):
        return {"content": "ok"}

    def chat_stream(self, _):
        yield "he"
        raise TimeoutError("boom mid-stream")


# -------- tests --------

def test_chat_retries_then_succeeds(monkeypatch):
    # no sleeping during tests
    monkeypatch.setattr("pai.resilience.resilient_provider.time.sleep", lambda *_: None)
    rp = ResilientProvider(FlakyThenOK(fail_times=2), ResiliencePolicy(max_retries=5, base_delay=0))
    assert rp.chat([])["content"] == "ok"


def test_chat_does_not_retry_on_non_retryable():
    class Bad:
        model = "bad"
        def chat(self, _): raise ValueError("nah")
        def chat_stream(self, _): yield "x"
    rp = ResilientProvider(Bad(), ResiliencePolicy(max_retries=3))
    with pytest.raises(RuntimeError):
        rp.chat([])


def test_total_timeout_enforced(monkeypatch):
    # Force elapsed time to exceed total_timeout immediately
    times = iter([0.0, 10.0, 10.0])
    monkeypatch.setattr("pai.resilience.resilient_provider.time.monotonic", lambda: next(times))
    monkeypatch.setattr("pai.resilience.resilient_provider.time.sleep", lambda *_: None)
    rp = ResilientProvider(FlakyThenOK(fail_times=10), ResiliencePolicy(max_retries=5, base_delay=0, total_timeout=0.1))
    with pytest.raises(RuntimeError):
        rp.chat([])


def test_stream_retries_only_before_first_chunk(monkeypatch):
    monkeypatch.setattr("pai.resilience.resilient_provider.time.sleep", lambda *_: None)
    rp = ResilientProvider(FlakyThenOK(fail_times=1, stream=True), ResiliencePolicy(max_retries=3, base_delay=0))
    assert list(rp.chat_stream([])) == ["ok"]


def test_stream_midway_failure_bubbles():
    rp = ResilientProvider(MidStreamBoom(), ResiliencePolicy())
    g = rp.chat_stream([])
    # first chunk yields
    assert next(g) == "he"
    # then failure becomes RuntimeError (not retried mid-stream)
    with pytest.raises(RuntimeError):
        next(g)


def test_keyboard_interrupt_passthrough_chat():
    class Kb:
        model = "kb"
        def chat(self, _): raise KeyboardInterrupt()
        def chat_stream(self, _): yield "x"
    rp = ResilientProvider(Kb(), ResiliencePolicy())
    with pytest.raises(KeyboardInterrupt):
        rp.chat([])


def test_keyboard_interrupt_passthrough_stream():
    class Kb2:
        model = "kb2"
        def chat(self, _): return {"content": "ok"}
        def chat_stream(self, _): raise KeyboardInterrupt()
    rp = ResilientProvider(Kb2(), ResiliencePolicy())
    with pytest.raises(KeyboardInterrupt):
        list(rp.chat_stream([]))
