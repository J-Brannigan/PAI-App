from openai import OpenAI

class OpenAIFunctionProvider:
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def chat(self, messages):

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            # tools= /None,
            # tool_choice="auto",
            temperature=0.2,
        )

        msg = resp.choices[0].message

        return {"content": msg.content or ""}
