from __future__ import annotations
from typing import Dict, Type, Callable, Any
from importlib import import_module
from importlib.metadata import entry_points

class ProviderRegistry:
    _classes: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Type], Type]:
        name = name.lower()
        def deco(klass: Type) -> Type:
            cls._classes[name] = klass
            return klass
        return deco

    @classmethod
    def get(cls, name: str) -> Type:
        key = name.lower()
        if key not in cls._classes:
            raise KeyError(f"Provider '{name}' not registered")
        return cls._classes[key]

    @classmethod
    def ensure_imports(cls) -> None:
        """
        Import built-in adapters so their @register decorators run.
        Call once at bootstrap before get().
        """
        import_module("pai.providers.openai_adapter")
        import_module("pai.providers.echo")
