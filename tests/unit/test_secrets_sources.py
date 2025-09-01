# tests/unit/test_secrets_sources.py

from __future__ import annotations
import sys, os
from pathlib import Path
import pytest

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pai.secrets.sources import (
    SecretsResolver,
    build_secret_sources,
)


def test_method_string_and_list(monkeypatch):
    # exact env var name via mapping
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    r1 = SecretsResolver(method="env", mapping={"openai": {"api_key": "OPENAI_API_KEY"}})
    assert r1.secret("openai") == "sk-env"

    # service name -> derived env var
    r2 = SecretsResolver(method=["env"], mapping={"openai": {"api_key": "openai"}})
    assert r2.secret("openai") == "sk-env"


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        build_secret_sources("nope")


def test_keyring_then_env(monkeypatch):
    # Prepare env fallback
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

    # Fake keyring that returns a value first
    class FakeKeyring:
        def get_credential(self, service, _):
            class Cred:
                password = "sk-from-keyring"
            return Cred()
        def get_password(self, *args, **kwargs):
            return None

    import pai.secrets.sources as src
    monkeypatch.setattr(src, "_keyring", FakeKeyring(), raising=True)

    r = SecretsResolver(method=["keyring", "env"], mapping={"openai": {"api_key": "openai"}})
    assert r.secret("openai") == "sk-from-keyring"

    # Now make keyring miss -> env wins
    class KR2:
        def get_credential(self, *_): return None
        def get_password(self, *_): return None
    monkeypatch.setattr(src, "_keyring", KR2(), raising=True)

    r2 = SecretsResolver(method=["keyring", "env"], mapping={"openai": {"api_key": "openai"}})
    assert r2.secret("openai") == "sk-from-env"
