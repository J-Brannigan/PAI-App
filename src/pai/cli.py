import typer
from pathlib import Path
from importlib.metadata import version as pkg_version, PackageNotFoundError

from .config import build_app
from .core.transcript import Transcript
from .core.chatSession import ChatSession
from .ui.banner import render_banner_from_config
from .ui.ui_config import load_ui_config, UIConfigError

app = typer.Typer(add_completion=False)

@app.callback(invoke_without_command=True)
def chat(config: Path = Path("config/default.yaml")):
    ctx = build_app(config)
    cfg = ctx['cfg'] or {}

    ui_cfg_path = (cfg.get("ui") or {}).get("config")

    if ui_cfg_path:
        ui_file = (config.parent / ui_cfg_path).resolve() if not Path(ui_cfg_path).is_absolute() else Path(ui_cfg_path)
        try:
            ui_cfg = load_ui_config(ui_file)
            try:
                app_ver = f"v{pkg_version('pai')}"
            except PackageNotFoundError:
                app_ver = None
            render_banner_from_config(ui_cfg, app_ver)
        except UIConfigError as e:
            print(f"[ui] {e}")

    storage = (cfg.get('storage') or {})

    transcripts_dir = storage.get("transcripts_dir")
    backend = (storage.get('backend') or 'file').lower()
    resume_id = storage.get('resume')

    system_prompt = (Path(__file__).parent / 'prompts' / 'system.txt').read_text(encoding='utf-8')

    transcript = Transcript(
        system_prompt=system_prompt,
        session_id=resume_id,  # None means new
        root_dir=Path(transcripts_dir) if backend == 'file' else None,
        header_meta={'config_path': str(config), 'model': getattr(ctx['model'], 'model', None)},
    )

    chat_session = ChatSession(model=ctx['model'], transcript=transcript)

    runtime = (cfg.get('runtime') or {})
    use_stream = bool(runtime.get('stream', False))

    print('PAI chat. Type /help for commands. Ctrl+C to quit.')
    while True:
        try:
            user_input = input('PAI> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nBye.')
            return

        if user_input in ('/exit', '/quit'):
            print('Bye.')
            return

        if user_input == '/help':
            print('Commands: /help, /id, /exit, /quit')
            continue

        if user_input == '/id':
            print(transcript.session_id)
            continue

        if use_stream:
            gen = chat_session.run_turn_stream(user_input)
            try:
                for piece in gen:
                    print(piece, end='', flush=True)
                print('')
            except KeyboardInterrupt:
                try:
                    gen.close()
                except Exception:
                    pass
                print('\n[stream interrupted]')
        else:
            reply = chat_session.run_turn(user_input)
            print(reply)

def run():
    app()
