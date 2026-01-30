from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pai.bootstrap import build_provider
from pai.config_loader import load_config, ConfigError
from pai.storage.transcript import Transcript
from pai.core.chat_session import ChatSession


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[3]


def _system_prompt() -> str:
    prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
    sys_prompt_path = prompts_dir / "system.txt"
    return sys_prompt_path.read_text(encoding="utf-8") if sys_prompt_path.exists() else "You're a helpful AI."


def create_app(
    config_path: Path,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> FastAPI:
    config_path = Path(config_path)
    cfg = load_config(config_path)

    if provider:
        cfg["model"]["provider"] = str(provider).lower()
        if cfg["model"]["provider"] not in ("openai", "echo"):
            raise ConfigError(
                f"Unknown model.provider '{cfg['model']['provider']}' (expected 'openai' or 'echo')."
            )
    if model:
        cfg["model"]["name"] = model

    provider_obj, warnings = build_provider(cfg, config_path)

    repo_root = _repo_root_from_here()
    tdir_raw = cfg["storage"]["transcripts_dir"]
    tdir_path = Path(tdir_raw)
    transcripts_dir = (repo_root / tdir_path).resolve() if not tdir_path.is_absolute() else tdir_path
    backend = cfg["storage"]["backend"]

    redact_enabled = bool((cfg.get("storage") or {}).get("redact", False))
    redact_fn = (lambda _s: "[REDACTED]") if redact_enabled else None

    app = FastAPI()
    app.state.cfg = cfg
    app.state.provider = provider_obj
    app.state.warnings = warnings
    app.state.system_prompt = _system_prompt()
    app.state.transcripts_dir = transcripts_dir if backend == "file" else None
    app.state.redact_fn = redact_fn
    app.state.context_cfg = cfg.get("context")
    app.state.sessions: Dict[str, ChatSession] = {}
    app.state.lock = threading.Lock()

    base_dir = Path(__file__).resolve().parent
    static_dir = base_dir / "static"
    index_path = base_dir / "index.html"

    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def _create_session() -> str:
        transcript = Transcript(
            system_prompt=app.state.system_prompt,
            root_dir=app.state.transcripts_dir,
            header_meta={
                "config_path": str(config_path),
                "provider": cfg["model"]["provider"],
                "model": cfg["model"]["name"],
            },
            redact=app.state.redact_fn,
        )
        chat_session = ChatSession(
            model=app.state.provider,
            transcript=transcript,
            context=app.state.context_cfg,
        )
        with app.state.lock:
            app.state.sessions[transcript.session_id] = chat_session
        return transcript.session_id

    def _get_session(session_id: Optional[str]) -> tuple[str, ChatSession]:
        if not session_id:
            new_id = _create_session()
            return new_id, app.state.sessions[new_id]
        with app.state.lock:
            session = app.state.sessions.get(session_id)
        if session is None:
            # If client sends an unknown id, create a fresh session
            new_id = _create_session()
            return new_id, app.state.sessions[new_id]
        return session_id, session

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/api/config")
    def api_config():
        return JSONResponse(
            {
                "provider": cfg["model"]["provider"],
                "model": cfg["model"]["name"],
                "stream": bool((cfg.get("runtime") or {}).get("stream", False)),
                "warnings": warnings or [],
            }
        )

    @app.post("/api/session")
    def api_session():
        return JSONResponse({"session_id": _create_session()})

    @app.post("/api/chat")
    def api_chat(req: ChatRequest):
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="Empty message")
        session_id, session = _get_session(req.session_id)
        reply = session.run_turn(req.message)
        return JSONResponse({"session_id": session_id, "reply": reply})

    @app.post("/api/stream")
    def api_stream(req: ChatRequest):
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="Empty message")
        session_id, session = _get_session(req.session_id)

        def gen():
            try:
                for chunk in session.run_turn_stream(req.message):
                    yield chunk
            except Exception as e:
                yield f"\n[error] {e}"

        return StreamingResponse(gen(), media_type="text/plain", headers={"X-Session-Id": session_id})

    return app


def run(
    *,
    config: Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    reload: bool = False,
) -> None:
    import uvicorn

    app = create_app(config, provider=provider, model=model)
    uvicorn.run(app, host=host, port=port, reload=reload)
