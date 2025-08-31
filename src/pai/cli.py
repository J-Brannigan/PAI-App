from __future__ import annotations
from pathlib import Path
from importlib.metadata import version as pkg_version, PackageNotFoundError
import typer

from .config import build_app
from .core.chatSession import ChatSession
from .core.transcript import Transcript

try:
    from .ui.ui_config import load_ui_config, UIConfigError  # type: ignore
    from .ui.banner import render_banner_from_config  # type: ignore
    HAVE_UI = True
except Exception:
    HAVE_UI = False

app = typer.Typer(add_completion=False)

# Anchor repo root from .../repo/src/pai/cli.py
REPO_ROOT = Path(__file__).resolve().parents[2]


@app.callback(invoke_without_command=True)
def chat(config: Path = Path("config/default.yaml")):
    # Build provider + load YAML
    ctx = build_app(config)
    cfg = ctx["cfg"] or {}

    # ----- Optional banner from ui.yaml -----
    if HAVE_UI:
        ui_cfg_rel = (cfg.get("ui") or {}).get("config")
        if ui_cfg_rel:
            config_dir = config.resolve().parent  # e.g. <repo>/config
            p = Path(ui_cfg_rel)
            ui_file = p if p.is_absolute() else (config_dir / p).resolve()

            try:
                ui_cfg = load_ui_config(ui_file)
                try:
                    app_ver = f"v{pkg_version('pai')}"
                except PackageNotFoundError:
                    app_ver = None
                render_banner_from_config(ui_cfg, app_ver)
            except UIConfigError as e:
                print(f"[ui] {e}")

    # ----- System prompt -----
    system_prompt_path = Path(__file__).parent / "prompts" / "system.txt"
    if system_prompt_path.exists():
        system_prompt = system_prompt_path.read_text(encoding="utf-8")
    else:
        system_prompt = "You're a helpful AI."

    # ----- Storage settings -----
    storage = cfg.get("storage") or {}
    backend = (storage.get("backend") or "file").lower()
    tdir_cfg = storage.get("transcripts_dir", "sessions")
    resume_id = storage.get("resume")  # may be None

    tdir_path = Path(tdir_cfg)
    transcripts_dir = tdir_path if tdir_path.is_absolute() else (REPO_ROOT / tdir_path)

    transcript = Transcript(
        system_prompt=system_prompt,
        session_id=resume_id,  # None => new session id
        root_dir=(transcripts_dir if backend == "file" else None),
        header_meta={
            "config_path": str(config),
            "model": getattr(ctx["model"], "model", None),
        },
    )

    # ----- Session -----
    chat_session = ChatSession(model=ctx["model"], transcript=transcript)

    # ----- Runtime -----
    runtime = cfg.get("runtime") or {}
    use_stream = bool(runtime.get("stream", False))

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
            print("Commands: /help, /id, /exit, /quit")
            continue

        if user_input == "/id":
            print(transcript.session_id)
            continue

        # Normal turn
        if use_stream:
            gen = chat_session.run_turn_stream(user_input)
            try:
                for piece in gen:
                    print(piece, end="", flush=True)
                print("")
            except KeyboardInterrupt:
                # Ensure finaliser persists partial
                try:
                    gen.close()
                except Exception:
                    pass
                print("\n[stream interrupted]")
        else:
            reply = chat_session.run_turn(user_input)
            print(reply)
