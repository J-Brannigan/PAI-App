from __future__ import annotations

class EchoProvider:
    """
    Offline fallback. It never calls tools. Just echoes short text.
    """
    def __init__(self, llm_log=None):
        self.llm_log = llm_log

    def chat(self, messages):
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return {"content": "Okay."}
