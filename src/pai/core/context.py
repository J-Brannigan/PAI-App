# src/pai/core/context.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from .ports import Message

# Optional: use tiktoken if present for better counts
try:
    import tiktoken
except Exception:
    tiktoken = None  # type: ignore


def _rough_token_count(text: str) -> int:
    # Fallback heuristic ≈ 4 chars/token
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


class TokenCounter:
    """
    Counts tokens for a list of OpenAI-style messages.
    Uses tiktoken when available; otherwise a simple heuristic.
    """
    def __init__(self, model_hint: Optional[str] = None):
        self.model_hint = model_hint or "gpt-4o-mini"
        self._enc = None
        if tiktoken is not None:
            try:
                # If the exact model isn't known to tiktoken, fall back to a common encoding
                self._enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._enc = None

    def count_text(self, text: str) -> int:
        if self._enc:
            try:
                return len(self._enc.encode(text))
            except Exception:
                pass
        return _rough_token_count(text)

    def count_messages(self, messages: List[Message]) -> int:
        # Very simple approximation: per-message overhead + content tokens
        total = 0
        for m in messages:
            # overhead ~ 4 (role, separators), conservative
            total += 4
            total += self.count_text(str(m.get("content", "")))
        return total


@dataclass(frozen=True)
class ContextPolicy:
    """
    max_input_tokens: hard cap for the request messages (pre-response).
    response_reserve_tokens: budget you want to leave for the model to answer.
    always_keep_last_n: always keep this many most-recent messages (in addition to system).
    """
    max_input_tokens: int
    response_reserve_tokens: int = 1024
    always_keep_last_n: int = 6  # user+assistant messages, not counting the initial system


class ContextWindowManager:
    """
    Trims old turns until the request fits within (max_input_tokens - response_reserve_tokens).
    Always keeps the very first system message and the last N messages.
    """
    def __init__(self, policy: ContextPolicy, model_hint: Optional[str] = None):
        self.policy = policy
        self.counter = TokenCounter(model_hint=model_hint)

    def apply(self, messages: List[Message], model_hint: Optional[str] = None) -> List[Message]:
        if not messages:
            return messages

        # Never drop the very first message if it's system
        system: List[Message] = []
        rest = messages
        if messages[0].get("role") == "system":
            system = [messages[0]]
            rest = messages[1:]

        # Quick path: if already within budget, return as-is
        target = self.policy.max_input_tokens - max(0, self.policy.response_reserve_tokens)
        target = max(1, target)  # sanity floor so we don't go to zero

        # If last-n is bigger than available messages, clamp
        keep_tail_n = min(self.policy.always_keep_last_n, len(rest))
        head = rest[:-keep_tail_n] if keep_tail_n > 0 else rest
        tail = rest[-keep_tail_n:] if keep_tail_n > 0 else []

        candidate = system + head + tail
        if self.counter.count_messages(candidate) <= target:
            return candidate

        # Trim from the head (oldest first), keeping system + tail intact
        drop_idx = 0
        head_len = len(head)
        while drop_idx < head_len and self.counter.count_messages(system + head[drop_idx:] + tail) > target:
            drop_idx += 1

        trimmed = system + head[drop_idx:] + tail

        # Safety: ensure at least the last user message is present
        if not any(m.get("role") == "user" for m in trimmed[-keep_tail_n:]) and any(m.get("role") == "user" for m in tail):
            # If we somehow trimmed away all users in tail (unlikely), force keep the very last user
            last_user_idx = max(i for i, m in enumerate(tail) if m.get("role") == "user")
            trimmed = system + head[drop_idx:] + tail[last_user_idx:]

        # Final guard: if still over target, progressively shorten tail
        while self.counter.count_messages(trimmed) > target and len(trimmed) > len(system) + 1:
            # drop the oldest of the remaining non-system messages
            trimmed = system + trimmed[len(system)+1:]

        return trimmed
