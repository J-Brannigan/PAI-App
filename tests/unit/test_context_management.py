# tests/unit/test_context_management.py

from __future__ import annotations
import sys
from pathlib import Path
from pprint import pformat

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pai.core.chat_session import ChatSession
from pai.storage.transcript import Transcript
import pai.core.context as ctx  # to monkeypatch ContextWindowManager.apply


class CapturingProvider:
    """
    Fake provider that captures the messages it was called with.
    """
    def __init__(self):
        self.model = "fake"
        self.last_messages = None

    def chat(self, messages):
        self.last_messages = [dict(m) for m in messages]  # shallow copy for assertions
        return {"content": "ok"}

    def chat_stream(self, messages):
        self.last_messages = [dict(m) for m in messages]
        yield "ok"


def _build_long_transcript():
    """
    Returns a Transcript with:
      system
      (user u0, assistant a0), ... , (user u9, assistant a9)
    """
    t = Transcript(system_prompt="sys", root_dir=None)
    for i in range(10):
        t.append_message("user", f"u{i}")
        t.append_message("assistant", f"a{i}")
    return t


def _wrap_apply_with_logging(monkeypatch, logs: list[dict]):
    """
    Monkeypatch ContextWindowManager.apply to record detailed diagnostics.
    """
    original_apply = ctx.ContextWindowManager.apply

    def debug_apply(self, messages, model_hint=None):
        # Compute target exactly as implementation does
        target = self.policy.max_input_tokens - max(0, self.policy.response_reserve_tokens)
        # IMPORTANT: mirror your code; if you changed the "floor", reflect it here
        target = max(1, target)

        before_len = len(messages)
        before_tokens = self.counter.count_messages(messages)

        out = original_apply(self, messages, model_hint=model_hint)

        after_len = len(out)
        after_tokens = self.counter.count_messages(out)

        entry = {
            "target": target,
            "before_len": before_len,
            "before_tokens": before_tokens,
            "after_len": after_len,
            "after_tokens": after_tokens,
            "kept_messages": out,
        }
        logs.append(entry)
        print("\n[CTX DEBUG] " + pformat(entry))  # printed so we see it on failure
        return out

    monkeypatch.setattr(ctx.ContextWindowManager, "apply", debug_apply, raising=True)


def _print_import_origins(cs: ChatSession):
    # Show where the classes were imported from (helps catch duplicate modules)
    cs_mod = cs.__class__.__module__
    mgr_mod = ctx.ContextWindowManager.__module__
    print(f"[IMPORTS] ChatSession module={cs_mod}")
    print(f"[IMPORTS] ContextWindowManager module={mgr_mod}")


def test_context_trims_head_keeps_system_and_tail(monkeypatch):
    """
    With a strict context policy, ChatSession should trim older turns and keep:
      - the system message
      - the last N messages (including the just-appended user)
    """
    t = _build_long_transcript()
    prov = CapturingProvider()

    # Configure trimming so that the full conversation is over budget,
    # but "system + last 4" fits.
    ctx_cfg = {
        "max_input_tokens": 50,         # small to force trimming
        "response_reserve_tokens": 0,   # make 'target' == 50 for this test
        "always_keep_last_n": 4,
    }
    cs = ChatSession(model=prov, transcript=t, context=ctx_cfg)
    assert cs.ctx_mgr is not None, "Context manager not initialised (context block not seen)"

    _print_import_origins(cs)

    # Wrap apply() for detailed logs
    logs: list[dict] = []
    _wrap_apply_with_logging(monkeypatch, logs)

    # Also verify apply() behaviour directly (pre-flight sanity)
    direct_out = cs.ctx_mgr.apply(t.messages)
    print("[DIRECT APPLY] kept messages:\n" + pformat(direct_out))

    # Trigger a new turn (appends 'user: now', then trims, then calls provider)
    out = cs.run_turn("now")
    assert out == "ok"

    # Must keep system as the first message
    assert prov.last_messages[0] == {"role": "system", "content": "sys"}

    # Must keep at least the last 4 messages (a8, u9, a9, now)
    expected_suffix = [
        {"role": "assistant", "content": "a8"},
        {"role": "user", "content": "u9"},
        {"role": "assistant", "content": "a9"},
        {"role": "user", "content": "now"},
    ]

    assert prov.last_messages[-4:] == expected_suffix


def test_context_disabled_sends_full_history():
    """
    Without a context policy, ChatSession should send the entire history
    (system + all prior messages + just-appended user).
    """
    t = _build_long_transcript()
    prov = CapturingProvider()

    # No context trimming
    cs = ChatSession(model=prov, transcript=t, context=None)

    # Trimming is OFF → ctx_mgr should be None
    assert cs.ctx_mgr is None

    # Before turn: system + 20 messages
    before_len = len(t.messages)

    cs.run_turn("hello")
    # Provider should receive everything that existed plus the new user (before the assistant reply is appended)
    assert prov.last_messages is not None
    print(f"[DISABLED] sent {len(prov.last_messages)} messages (expected {before_len + 1})")
    assert len(prov.last_messages) == before_len + 1
    # The last message sent should be the new user
    assert prov.last_messages[-1] == {"role": "user", "content": "hello"}


def test_context_applies_to_streaming_too(monkeypatch):
    """
    The same trimming should apply in the streaming path (messages passed to chat_stream).
    """
    t = _build_long_transcript()
    prov = CapturingProvider()

    ctx_cfg = {
        "max_input_tokens": 50,
        "response_reserve_tokens": 0,
        "always_keep_last_n": 4,
    }
    cs = ChatSession(model=prov, transcript=t, context=ctx_cfg)
    assert cs.ctx_mgr is not None, "Context manager not initialised (context block not seen)"
    _print_import_origins(cs)

    # Wrap apply() for detailed logs
    logs: list[dict] = []
    _wrap_apply_with_logging(monkeypatch, logs)

    chunks = list(cs.run_turn_stream("stream-now"))
    assert "".join(chunks) == "ok"

    # Must keep system as the first message
    assert prov.last_messages[0] == {"role": "system", "content": "sys"}

    # Must keep at least the last 4 messages (a8, u9, a9, stream-now)
    expected_suffix = [
        {"role": "assistant", "content": "a8"},
        {"role": "user", "content": "u9"},
        {"role": "assistant", "content": "a9"},
        {"role": "user", "content": "stream-now"},
    ]
    assert prov.last_messages[-4:] == expected_suffix
