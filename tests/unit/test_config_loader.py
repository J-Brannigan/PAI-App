# tests/test_config_loader.py

from __future__ import annotations
import sys
from pathlib import Path
import pytest
from textwrap import dedent

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pai.config_loader import load_config, ConfigError  # type: ignore


def write_yaml(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(text).lstrip("\n").rstrip() + "\n", encoding="utf-8")
    return p


def test_load_config_ok(tmp_path: Path):
    cfg = write_yaml(
        tmp_path / "config" / "default.yaml",
        """
        model: { provider: OPENAI, name: gpt-4o-mini }
        storage: { backend: FILE, transcripts_dir: sessions, resume: null }
        runtime: { stream: true }
        """,
    )
    data = load_config(cfg)
    assert data["model"]["provider"] == "openai"   # normalised
    assert data["storage"]["backend"] == "file"    # normalised
    # loader leaves paths as provided (bootstrap resolves them)
    assert data["storage"]["transcripts_dir"] == "sessions"


def test_load_config_missing_key(tmp_path: Path):
    cfg = write_yaml(
        tmp_path / "config" / "default.yaml",
        """
        model: { name: gpt-4o-mini }         # missing provider
        storage: { backend: file, transcripts_dir: sessions }
        runtime: { stream: true }
        """,
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_load_config_type_error(tmp_path: Path):
    cfg = write_yaml(
        tmp_path / "config" / "default.yaml",
        """
        model: { provider: openai, name: gpt-4o-mini }
        storage: { backend: file, transcripts_dir: sessions }
        runtime: { stream: "yes" }   # wrong type
        """,
    )
    with pytest.raises(ConfigError):
        load_config(cfg)
