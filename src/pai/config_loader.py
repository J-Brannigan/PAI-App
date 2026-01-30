# src/pai/config_loader.py

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
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


def _validate_keys(d: Dict[str, Any], allowed: Iterable[str], section: str) -> None:
    allowed_set = set(allowed)
    for k in d.keys():
        if k not in allowed_set:
            raise ConfigError(f"Unknown config key: {section}.{k}")


def _require_dict(d: Dict[str, Any], key: str) -> Dict[str, Any]:
    val = d.get(key)
    if not isinstance(val, dict):
        raise ConfigError(f"'{key}' must be a mapping")
    return val


def _optional_bool(d: Dict[str, Any], key: str, section: str) -> Optional[bool]:
    if key not in d:
        return None
    val = d.get(key)
    if not isinstance(val, bool):
        raise ConfigError(f"'{section}.{key}' must be a boolean")
    return val


def _optional_str(d: Dict[str, Any], key: str, section: str) -> Optional[str]:
    if key not in d:
        return None
    val = d.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise ConfigError(f"'{section}.{key}' must be a string or null")
    return val


def _optional_int(d: Dict[str, Any], key: str, section: str) -> Optional[int]:
    if key not in d:
        return None
    val = d.get(key)
    if not isinstance(val, int):
        raise ConfigError(f"'{section}.{key}' must be an integer")
    return val


def load_config(path: Path) -> Dict[str, Any]:
    if not path or not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(f"Config is empty or invalid YAML: {path}")

    allowed_top = {
        "model",
        "providers",
        "secrets",
        "storage",
        "runtime",
        "ui",
        "context",
        "logging",
    }
    for k in raw.keys():
        if k not in allowed_top:
            raise ConfigError(f"Unknown config key: {k}")

    # Validate required keys (no defaults here)
    _require(raw, "model.provider", str)
    _require(raw, "model.name", str)
    _require(raw, "storage.backend", str)          # 'file' or 'none'
    _require(raw, "storage.transcripts_dir", str)  # path string
    _require(raw, "runtime.stream", bool)

    # Validate top-level sections
    model_cfg = _require_dict(raw, "model")
    _validate_keys(model_cfg, {"provider", "name"}, "model")

    storage_cfg = _require_dict(raw, "storage")
    _validate_keys(storage_cfg, {"backend", "transcripts_dir", "resume", "redact"}, "storage")
    _optional_str(storage_cfg, "resume", "storage")
    _optional_bool(storage_cfg, "redact", "storage")

    runtime_cfg = _require_dict(raw, "runtime")
    _validate_keys(runtime_cfg, {"stream"}, "runtime")

    if "secrets" in raw:
        secrets_cfg = _require_dict(raw, "secrets")
        _validate_keys(secrets_cfg, {"method", "mapping"}, "secrets")
        method = secrets_cfg.get("method")
        if method is not None and not isinstance(method, (str, list, tuple)):
            raise ConfigError("'secrets.method' must be a string or list")
        if isinstance(method, (list, tuple)):
            if not all(isinstance(m, str) for m in method):
                raise ConfigError("'secrets.method' list items must be strings")
        mapping = secrets_cfg.get("mapping")
        if mapping is not None and not isinstance(mapping, dict):
            raise ConfigError("'secrets.mapping' must be a mapping")

    if "ui" in raw:
        ui_cfg = _require_dict(raw, "ui")
        _validate_keys(ui_cfg, {"config"}, "ui")
        _optional_str(ui_cfg, "config", "ui")

    if "context" in raw:
        context_cfg = _require_dict(raw, "context")
        _validate_keys(context_cfg, {"max_input_tokens", "response_reserve_tokens", "always_keep_last_n"}, "context")
        _optional_int(context_cfg, "max_input_tokens", "context")
        _optional_int(context_cfg, "response_reserve_tokens", "context")
        _optional_int(context_cfg, "always_keep_last_n", "context")

    if "logging" in raw:
        logging_cfg = _require_dict(raw, "logging")
        _validate_keys(logging_cfg, {"level", "notices", "rich"}, "logging")
        _optional_str(logging_cfg, "level", "logging")
        _optional_bool(logging_cfg, "rich", "logging")
        if "notices" in logging_cfg and not isinstance(logging_cfg.get("notices"), (str, bool, type(None))):
            raise ConfigError("'logging.notices' must be a string, boolean, or null")

    if "providers" in raw:
        providers_cfg = _require_dict(raw, "providers")
        for pname, pcfg in providers_cfg.items():
            if not isinstance(pcfg, dict):
                raise ConfigError(f"'providers.{pname}' must be a mapping")
            if pname == "openai":
                _validate_keys(
                    pcfg,
                    {"params", "timeout", "strict_params", "debug_params", "base_url", "organization", "policy_file"},
                    "providers.openai",
                )
                if "params" in pcfg and not isinstance(pcfg.get("params"), dict):
                    raise ConfigError("'providers.openai.params' must be a mapping")
                if "timeout" in pcfg and not isinstance(pcfg.get("timeout"), (int, float)):
                    raise ConfigError("'providers.openai.timeout' must be a number")
                _optional_bool(pcfg, "strict_params", "providers.openai")
                _optional_bool(pcfg, "debug_params", "providers.openai")
                _optional_str(pcfg, "base_url", "providers.openai")
                _optional_str(pcfg, "organization", "providers.openai")
                _optional_str(pcfg, "policy_file", "providers.openai")
            elif pname == "echo":
                _validate_keys(pcfg, {"token_delay"}, "providers.echo")
                if "token_delay" in pcfg and not isinstance(pcfg.get("token_delay"), (int, float)):
                    raise ConfigError("'providers.echo.token_delay' must be a number")

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
