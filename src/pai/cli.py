import typer
from pathlib import Path
from .config import build_app
from .core.chatSession import ChatSession

app = typer.Typer(add_completion=False)

@app.callback(invoke_without_command=True)
def chat(config: Path = Path("config/default.yaml")):
    ctx = build_app(config)
    chat_session = ChatSession(
        model=ctx["model"],
        prompt_path=Path(__file__).parent / "prompts" / "system.txt",
    )
    print("PAI chat. Type /help for commands. Ctrl+C to quit.")
    while True:
        try:
            user_input = input("PAI> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if user_input in ("/exit", "/quit"):
            print("Bye.")
            return
        if user_input == "/help":
            print("Commands: /help")
            continue

        reply = chat_session.run_turn(user_input)
        print(reply)

def run():
    app()
