# src/pai/providers/openai.py
from __future__ import annotations
from openai import OpenAI

class OpenAIFunctionProvider:
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def chat(self, messages):
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        msg = resp.choices[0].message
        return {"content": msg.content or ""}

    def chat_stream(self, messages):
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            stream=True,
        )
        for chunk in stream:
            # Defensive parsing across SDK minor changes
            try:
                choice = chunk.choices[0]
            except Exception:
                continue

            # Preferred: delta.content as tokens arrive
            delta = getattr(choice, "delta", None)
            if delta is not None:
                piece = getattr(delta, "content", None)
                if piece:
                    yield piece
                    continue

            # Fallbacks some SDKs have exposed in the past
            piece = getattr(choice, "text", None)
            if piece:
                yield piece
