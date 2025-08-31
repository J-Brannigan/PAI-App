import typer
from pathlib import Path
from importlib.metadata import version as pkg_version, PackageNotFoundError

from .bootstrap import build_app
from .core.chat_session import ChatSession

# Optional UI banner
try:
    from .ui.ui_config import load_ui_config, UIConfigError  # type: ignore
    from .ui.banner import render_banner_from_config  # type: ignore
    HAVE_UI = True
except Exception:
    HAVE_UI = False

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def chat(config: Path = Path("config/default.yaml")) -> None:
    """
    Start the PAI REPL.
    """
    try:
        ctx = build_app(config)
    except Exception as e:
        print(f"[fatal] {e}")
        raise typer.Exit(code=1)

    cfg = ctx["cfg"]
    paths = ctx["paths"]
    provider = ctx["provider"]
    transcript = ctx["transcript"]

    # ----- Optional banner from ui.yaml (path resolved relative to config folder) -----
    if HAVE_UI:
        ui_cfg_rel = (cfg.get("ui") or {}).get("config")
        if ui_cfg_rel:
            config_dir = paths["config_dir"]
            ui_path = Path(ui_cfg_rel)
            ui_file = ui_path if ui_path.is_absolute() else (config_dir / ui_path).resolve()
            try:
                ui_cfg = load_ui_config(ui_file)
                try:
                    app_ver = f"v{pkg_version('pai')}"
                except PackageNotFoundError:
                    app_ver = None
                render_banner_from_config(ui_cfg, app_ver)
            except UIConfigError as e:
                print(f"[ui] {e}")

    # ----- Session -----
    chat_session = ChatSession(model=provider, transcript=transcript)

    # ----- Runtime flags -----
    runtime = cfg.get("runtime") or {}
    use_stream = bool(runtime.get("stream", False))

    print("PAI chat. Type /help for commands. Ctrl+C to quit.")
    while True:
        try:
            user_input = input("PAI> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            transcript.close()
            return

        if not user_input:
            continue

        if user_input in ("/exit", "/quit"):
            print("Bye.")
            transcript.close()
            return

        if user_input == "/help":
            print("Commands: /help, /id, /exit, /quit")
            continue

        if user_input == "/id":
            # Transcript owns the canonical id
            try:
                print(transcript.session_id)  # type: ignore[attr-defined]
            except Exception:
                print("[warn] no session id available")
            continue

        # ----- Normal turn -----
        if use_stream:
            gen = chat_session.run_turn_stream(user_input)
            try:
                for piece in gen:
                    print(piece, end="", flush=True)
                print("")
            except KeyboardInterrupt:
                # Ensure finaliser runs to persist partial
                try:
                    gen.close()
                except Exception:
                    pass
                print("\n[stream interrupted]")
        else:
            reply = chat_session.run_turn(user_input)
            print(reply)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
