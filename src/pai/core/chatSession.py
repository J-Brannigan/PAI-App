import datetime as dt
from typing import List, Dict

class ChatSession:
    def __init__(self, model, prompt_path):
        self.messages: List[Dict[str, str]] = []
        self.model = model
        self.prompt_path = prompt_path
        self.messages =[{"role": "system", "content":self._system_prompt()}]
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.id = ts

    def _system_prompt(self) -> str:
        prompt = self.prompt_path.read_text(encoding="utf-8")
        return prompt

    def _call_model(self, messages):
        reply = self.model.chat(messages)
        return reply

    def run_turn(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})

        reply = self._call_model(self.messages)

        # If reply is already a dict:
        if isinstance(reply, dict):
            reply_content = reply["content"]
        else:
            # If reply is a string (plain text):
            reply_content = reply

        self.messages.append({"role": "assistant", "content": reply_content})

        return reply_content
