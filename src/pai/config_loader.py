# src/pai/config_loader.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import yaml


class ConfigError(ValueError):
    pass


def _require(d: Dict[str, Any], dotted: str, typ: type) -> Any:
    cur: Any = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            raise ConfigError(f"Missing config key: {dotted}")
        cur = cur[k]
    if typ is bool and not isinstance(cur, bool):
        raise ConfigError(f"'{dotted}' must be a boolean")
    if typ is str and not isinstance(cur, str):
        raise ConfigError(f"'{dotted}' must be a string")
    return cur


def load_config(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(f"Config is empty or invalid YAML: {path}")

    # Validate required keys (no defaults here)
    _require(raw, "model.provider", str)
    _require(raw, "model.name", str)
    _require(raw, "storage.backend", str)          # 'file' or 'none'
    _require(raw, "storage.transcripts_dir", str)  # path string
    _require(raw, "runtime.stream", bool)

    # Normalise enumerations
    provider = str(raw["model"]["provider"]).lower()
    backend = str(raw["storage"]["backend"]).lower()
    if provider not in ("openai", "echo"):
        raise ConfigError(f"Unknown model.provider '{provider}' (expected 'openai' or 'echo').")
    if backend not in ("file", "none"):
        raise ConfigError(f"Unknown storage.backend '{backend}' (expected 'file' or 'none').")
    raw["model"]["provider"] = provider
    raw["storage"]["backend"] = backend

    # Leave paths as provided; resolve them later in bootstrap/composition
    return raw
