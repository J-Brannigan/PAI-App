from __future__ import annotations
from typing import List, Dict, Any, Optional
from .context import ContextWindowManager, ContextPolicy

class ChatSession:
    def __init__(self, model, transcript, context: Optional[dict] = None):
        self.model = model
        self.transcript = transcript

        self.ctx_mgr: Optional[ContextWindowManager] = None
        if context:
            policy = ContextPolicy(
                max_input_tokens=int(context.get("max_input_tokens")),
                response_reserve_tokens=int(context.get("response_reserve_tokens", 1024)),
                always_keep_last_n=int(context.get("always_keep_last_n", 6)),
            )
            self.ctx_mgr = ContextWindowManager(policy, model_hint=getattr(self.model, "model", None))

    def _outgoing_messages(self) -> List[Dict[str, Any]]:
        msgs = self.transcript.messages
        return self.ctx_mgr.apply(msgs) if self.ctx_mgr else msgs

    def run_turn(self, user_text: str) -> str:
        self.transcript.append_message("user", user_text)
        messages = self._outgoing_messages()          # ← use trimmed view
        reply = self.model.chat(messages)
        content = reply["content"] if isinstance(reply, dict) else str(reply)
        self.transcript.append_message("assistant", content)
        return content

    def run_turn_stream(self, user_text: str):
        self.transcript.append_message("user", user_text)
        messages = self._outgoing_messages()          # ← use trimmed view
        partial: list[str] = []

        def gen():
            try:
                for piece in self.model.chat_stream(messages):
                    partial.append(piece)
                    yield piece
            finally:
                if partial:
                    self.transcript.append_message("assistant", "".join(partial))
        return gen()
