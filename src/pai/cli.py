import typer
from pathlib import Path
from importlib.metadata import version as pkg_version, PackageNotFoundError
from typing import Optional

from .bootstrap import build_app
from .core.chat_session import ChatSession

# Optional UI banner
try:
    from .ui.ui_config import load_ui_config, UIConfigError  # type: ignore
    from .ui.banner import render_banner_from_config  # type: ignore
    HAVE_UI = True
except Exception:
    HAVE_UI = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    HAVE_RICH = True
except Exception:
    HAVE_RICH = False

app = typer.Typer(add_completion=False)

def _normalise_notices(val) -> str:
    if isinstance(val, bool):
        return "off" if val is False else "full"  # True → treat as “full”
    if val is None:
        return "full"
    s = str(val).strip().lower()
    mapping = {
        "off": "off", "quiet": "off", "silent": "off", "none": "off",
        "0": "off", "false": "off", "no": "off",
        "brief": "brief", "short": "brief", "compact": "brief",
        "full": "full", "on": "full", "true": "full", "yes": "full", "1": "full",
    }
    return mapping.get(s, "full")


@app.callback(invoke_without_command=True)
def chat(
    config: Path = typer.Option(Path("config/default.yaml"), "--config", "-c"),
    provider: Optional[str] = typer.Option(None, "--provider", help="Override model.provider"),
    model: Optional[str] = typer.Option(None, "--model", help="Override model.name"),
    stream: bool = typer.Option(False, "--stream", help="Force streaming on"),
    no_stream: bool = typer.Option(False, "--no-stream", help="Force streaming off"),
) -> None:
    """
    Start the PAI REPL.
    """
    try:
        if stream and no_stream:
            print("[fatal] Cannot use both --stream and --no-stream")
            raise typer.Exit(code=2)
        stream_override = True if stream else False if no_stream else None
        ctx = build_app(config, provider=provider, model=model, stream=stream_override)
    except Exception as e:
        print(f"[fatal] {e}")
        raise typer.Exit(code=1)

    cfg = ctx["cfg"]
    paths = ctx["paths"]
    provider = ctx["provider"]
    transcript = ctx["transcript"]
    context_cfg = cfg.get("context")
    warnings = ctx.get("warnings")

    logging_cfg = (cfg.get("logging") or {})
    notices_mode = _normalise_notices(logging_cfg.get("notices", "full"))
    use_rich = bool(logging_cfg.get("rich", True))

    def _render_notices(notices):
        if not notices or notices_mode == "off":
            return
        lines = []
        for n in notices:
            if n.get("type") == "policy_drop":
                dropped_keys = ", ".join(n["dropped"].keys())
                if notices_mode == "brief":
                    lines.append(f"[{n['provider']}] dropped: {dropped_keys} for {n['model']} (from {n['source']})")
                else:  # full
                    detail = "\n    ".join(f"{k}={repr(v)}" for k, v in n["dropped"].items())
                    lines.append(
                        f"[{n['provider']}] {n['message']}\n"
                        f"    model:  {n['model']}\n"
                        f"    dropped:\n"
                        f"    {detail}\n"
                        f"    source: {n['source']}\n"
                        f"    policy: {n['policy']}\n"
                        f"    hint: set providers.{n['provider']}.strict_params: true to fail fast."
                    )
            else:
                # fallback for unknown notice types
                lines.append(str(n))

            msg = "\n".join(f"⚠️  {line}" for line in lines)

            if use_rich and HAVE_RICH:
                from rich.console import Console
                from rich.panel import Panel
                from rich.text import Text
                Console().print(
                    Panel(Text(msg, style="bold yellow"),
                          title="[bold yellow]Session warnings",
                          border_style="yellow",
                          expand=True)
                )
            else:
                for line in lines:
                    typer.secho(f"WARNING: {line}", fg=typer.colors.YELLOW, bold=True)

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

    _render_notices(warnings)

    # ----- Session -----
    chat_session = ChatSession(
        model=ctx["provider"],
        transcript=ctx["transcript"],
        context=context_cfg,
    )

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
