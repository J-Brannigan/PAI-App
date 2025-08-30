# src/pai/config.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv

from .providers.openai import OpenAIFunctionProvider
from .providers.echo import EchoProvider
from .utils.secrets import get_openai_api_key

load_dotenv()


def _get(d: Dict[str, Any], dotted: str) -> Any:
    cur: Any = d
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            raise ValueError(f"Missing config key '{dotted}'")
        cur = cur[key]
    return cur


def load_config(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"Config is empty or invalid YAML: {path}")

    # Validate required keys and basic types (no defaults here)
    errors: list[str] = []
    required = {
        "model.provider": str,
        "model.name": str,
        "storage.backend": str,          # 'file' or 'none'
        "storage.transcripts_dir": str,  # path string
        "runtime.stream": bool,
    }
    for dotted, typ in required.items():
        try:
            val = _get(raw, dotted)
            if typ is bool and not isinstance(val, bool):
                errors.append(f"'{dotted}' must be a boolean")
            elif typ is str and not isinstance(val, str):
                errors.append(f"'{dotted}' must be a string")
        except ValueError as e:
            errors.append(str(e))

    if errors:
        raise ValueError("Invalid config:\n  " + "\n  ".join(errors))

    # Normalise some values
    provider = _get(raw, "model.provider").lower()
    raw["model"]["provider"] = provider
    backend = _get(raw, "storage.backend").lower()
    raw["storage"]["backend"] = backend

    # Validate enumerations without assigning defaults
    if provider not in ("openai", "echo"):
        raise ValueError(f"Unknown provider '{provider}'. Expected 'openai' or 'echo'.")
    if backend not in ("file", "none"):
        raise ValueError(f"Unknown storage.backend '{backend}'. Expected 'file' or 'none'.")

    # Resolve transcripts_dir relative to the config file
    base_dir = path.parent
    tdir = _get(raw, "storage.transcripts_dir")
    raw["storage"]["transcripts_dir"] = tdir

    return raw


def build_app(config_path: Path):
    cfg = load_config(config_path)

    provider = cfg["model"]["provider"]
    model_name = cfg["model"]["name"]

    if provider == "openai":
        api_key = get_openai_api_key()
        if not api_key:
            raise ValueError("OpenAI API key could not be found")
        model = OpenAIFunctionProvider(model=model_name, api_key=api_key)

    elif provider == "echo":
        model = EchoProvider()

    else:
        # Should be unreachable due to earlier validation
        raise ValueError(f"Unknown provider: {provider}")

    return {
        "cfg": cfg,   # use in CLI for storage/runtime decisions
        "model": model,
    }
