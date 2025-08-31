from __future__ import annotations
from typing import Iterable

class ChatSession:
    def __init__(self, model, transcript):
        self.model = model
        self.transcript = transcript  # instance of Transcript

    def _call_model(self, messages):
        return self.model.chat(messages)

    def run_turn(self, user_text: str) -> str:
        self.transcript.append_message('user', user_text, status='complete')
        reply = self._call_model(self.transcript.messages)
        text = reply['content'] if isinstance(reply, dict) else reply
        self.transcript.append_message('assistant', text, status='complete')
        return text

    def run_turn_stream(self, user_text: str) -> Iterable[str]:
        self.transcript.append_message('user', user_text, status='complete')
        chunks: list[str] = []

        def _gen():
            try:
                if hasattr(self.model, 'chat_stream'):
                    for piece in self.model.chat_stream(self.transcript.messages):
                        if piece:
                            chunks.append(piece)
                            yield piece
                else:
                    reply = self._call_model(self.transcript.messages)
                    text = reply['content'] if isinstance(reply, dict) else reply
                    chunks.append(text)
                    yield text
            finally:
                text = ''.join(chunks)
                status = 'complete' if text else 'partial'
                self.transcript.append_message('assistant', text, status=status)

        return _gen()
