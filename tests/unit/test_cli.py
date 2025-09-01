# tests/test_cli.py

from __future__ import annotations
import sys
from pathlib import Path
from typer.testing import CliRunner

# Ensure "src" is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pai.cli import app  # Typer app


def test_cli_echo_roundtrip(tmp_path: Path, monkeypatch):
    # Arrange config that uses echo provider and absolute sessions dir
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True)
    sessions_dir = tmp_path / "sessions"
    cfg = cfg_dir / "default.yaml"
    cfg.write_text(
        f"""
        model:
          provider: echo
          name: echo-model
        providers:
          echo:
            token_delay: 0.0
        secrets:
          method: env
          mapping: {{}}
        storage:
          backend: file
          transcripts_dir: "{sessions_dir}"
          resume: null
        runtime:
          stream: true
        """,
        encoding="utf-8",
    )

    runner = CliRunner()
    # Provide a minimal dialogue: one message, then exit
    result = runner.invoke(app, ["--config", str(cfg)], input="hello\n/exit\n", catch_exceptions=False)

    assert result.exit_code == 0
    # Echo provider returns a fixed lorem ipsum; check a known word appears
    assert "Lorem ipsum" in result.output or "lorem ipsum" in result.output.lower()
    # Sessions folder should be created at the absolute path
    assert sessions_dir.exists() and sessions_dir.is_dir()
