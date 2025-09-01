# tests/test_registry.py

from __future__ import annotations
import sys
from pathlib import Path

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pai.providers.registry import ProviderRegistry  # type: ignore


def test_registry_register_and_get():
    @ProviderRegistry.register("Dummy")
    class DummyProvider:
        @classmethod
        def create(cls, *, model_name, provider_cfg, secrets):
            return cls()
        def chat(self, messages): return {"content": "ok"}
        def chat_stream(self, messages):
            yield "ok"

    # Case-insensitive lookup
    cls_lower = ProviderRegistry.get("dummy")
    cls_upper = ProviderRegistry.get("DUMMY")
    assert cls_lower is DummyProvider
    assert cls_upper is DummyProvider

def test_registry_unknown_raises():
    try:
        ProviderRegistry.get("does-not-exist")
        assert False, "Expected KeyError"
    except KeyError:
        pass
