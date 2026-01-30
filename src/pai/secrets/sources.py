# src/pai/secrets/sources.py

from __future__ import annotations
from typing import Protocol, Optional, Dict, Iterable, List, Union
import os, sys, getpass, subprocess

try:
    import keyring as _keyring
except Exception:
    _keyring = None  # optional

class SecretSource(Protocol):
    def get(self, service: str) -> Optional[str]: ...

class EnvSource:
    def get(self, service: str) -> Optional[str]:
        # Allow mapping to be an explicit env var key OR a service name
        # 1) exact env var name
        val = os.getenv(service)
        if val:
            return val.strip()
        # 2) derived names
        for key in (f"{service.upper()}_API_KEY", service.upper()):
            val = os.getenv(key)
            if val:
                return val.strip()
        return None

class SystemKeyringSource:
    def get(self, service: str) -> Optional[str]:
        if _keyring is not None and hasattr(_keyring, "get_credential"):
            try:
                cred = _keyring.get_credential(service, None)  # type: ignore[arg-type]
                if cred and getattr(cred, "password", None):
                    return cred.password.strip()
            except Exception:
                pass
        if _keyring is not None:
            for account in ("API_KEY", "OPENAI_API_KEY", "default", service, getpass.getuser()):
                try:
                    val = _keyring.get_password(service, account)
                    if val:
                        return val.strip()
                except Exception:
                    pass
        if sys.platform == "darwin":
            try:
                p = subprocess.run(
                    ["security", "find-generic-password", "-s", service, "-w"],
                    capture_output=True, text=True, check=False
                )
                if p.returncode == 0 and p.stdout.strip():
                    return p.stdout.strip()
            except Exception:
                pass
        return None

_ALLOWED_METHODS = {"env", "keyring"}

def _normalise_methods(method: Union[str, Iterable[str]]) -> List[str]:
    if isinstance(method, str):
        methods = [method]
    else:
        methods = list(method)
    norm = []
    for m in methods:
        key = str(m).strip().lower()
        if key not in _ALLOWED_METHODS:
            raise ValueError(f"Unknown secrets method '{m}'. Allowed: {sorted(_ALLOWED_METHODS)}")
        if key not in norm:
            norm.append(key)
    return norm

def build_secret_sources(method: Union[str, Iterable[str]]) -> List[SecretSource]:
    sources: List[SecretSource] = []
    for name in _normalise_methods(method):
        if name == "env":
            sources.append(EnvSource())
        elif name == "keyring":
            sources.append(SystemKeyringSource())
    return sources

class SecretsResolver:
    """
    Resolve secrets using one or more methods in order.
    mapping: per-provider map of names -> service/env-key
      e.g. { "openai": { "api_key": "openai" } } or { "openai": { "api_key": "OPENAI_API_KEY" } }
    """
    def __init__(self, method: Union[str, Iterable[str]], mapping: Dict[str, Dict[str, str]] | None = None):
        self._sources = build_secret_sources(method)
        self._map = mapping or {}

    def secret(self, provider: str, name: str = "api_key") -> Optional[str]:
        service = self._map.get(provider, {}).get(name, provider)
        for src in self._sources:
            val = src.get(service)
            if val:
                return val
        return None
