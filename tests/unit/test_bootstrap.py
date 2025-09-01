# tests/test_bootstrap.py

from __future__ import annotations
import sys
from pathlib import Path

# Ensure "src" is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pai.bootstrap import build_app
from pai.resilience.resilient_provider import ResilientProvider


def test_build_app_echo(tmp_path: Path):
    # Arrange: temp repo with config/default.yaml and absolute sessions dir
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True)
    sessions_dir = tmp_path / "sessions"
    cfg = cfg_dir / "default.yaml"
    cfg.write_text(
        """
        model:
          provider: echo
          name: echo-model
        providers:
          echo:
            token_delay: 0.0
        secrets:
          method: env
          mapping: {}
        storage:
          backend: file
          transcripts_dir: "%s"
          resume: null
        runtime:
          stream: true
        """
        % str(sessions_dir),
        encoding="utf-8",
    )

    # Act
    ctx = build_app(cfg, repo_root=tmp_path)

    # Assert
    assert isinstance(ctx["provider"], ResilientProvider)
    assert ctx["paths"]["transcripts_dir"] == sessions_dir
    assert ctx["cfg"]["model"]["provider"] == "echo"
    assert (sessions_dir.exists() and sessions_dir.is_dir())
