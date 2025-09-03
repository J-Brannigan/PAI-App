from __future__ import annotations
import sys
from pathlib import Path
import yaml

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pai.providers.registry import ProviderRegistry
from pai.core.errors import ProviderClientError


def write_yaml(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")
    return p


class FakeAdapter:
    captured_params = None
    created = False

    @classmethod
    def create(cls, *, model_name: str, provider_cfg: dict, secrets):
        cls.created = True
        cls.captured_params = dict(provider_cfg.get("params") or {})
        class _Obj:
            model = model_name
            def chat(self, messages): return {"content": "ok"}
            def chat_stream(self, messages):
                yield "ok"
        return _Obj()


def _build_cfg_yaml(policy_file: Path, params: dict, stream: bool) -> str:
    cfg_dict = {
        "model": {"provider": "openai", "name": "gpt-5-nano-2025-08-07"},
        "providers": {
            "openai": {
                "params": params,
                "policy_file": str(policy_file),
                "timeout": 10,
            }
        },
        "secrets": {"method": "env", "mapping": {"openai": {"api_key": "OPENAI_API_KEY"}}},
        "storage": {"backend": "file", "transcripts_dir": "sessions"},
        "runtime": {"stream": stream},
    }
    return yaml.safe_dump(cfg_dict, sort_keys=False)


def _assert_notice_mentions_dropped_keys(notices, keys: set[str]) -> None:
    assert notices, "Expected at least one notice"
    # If structured notices (dicts) exist, prefer them
    for n in notices:
        if isinstance(n, dict) and n.get("type") == "policy_drop":
            dropped = set((n.get("dropped") or {}).keys())
            assert keys.issubset(dropped), f"Notice missing dropped keys {keys - dropped}"
            return
    # Otherwise, fall back to string containment
    joined = " ".join(str(n) for n in notices)
    for k in keys:
        assert k in joined, f"Notice string missing key: {k}"


def test_bootstrap_applies_drop_policy_once_and_filters_params(tmp_path: Path, monkeypatch):
    # Policy that drops sampling knobs for nano models
    policy_file = write_yaml(
        tmp_path / "config" / "providers" / "openai.yaml",
        """
        rules:
          - when_model_matches: "^gpt-5-nano"
            action: drop
            params: [temperature, top_p]
            message: "Nano models use default sampling only."
        """,
    )

    cfg_file = write_yaml(
        tmp_path / "config" / "default.yaml",
        _build_cfg_yaml(policy_file, {"temperature": 0.2, "top_p": 0.9, "keep": "ok"}, stream=True),
    )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # Don’t import the real adapter
    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: FakeAdapter))

    from pai.bootstrap import build_app
    app = build_app(cfg_file)

    # Adapter was created and received filtered params
    assert FakeAdapter.created is True
    assert FakeAdapter.captured_params == {"keep": "ok"}

    # App returned a notice that mentions the dropped keys
    _assert_notice_mentions_dropped_keys(app.get("warnings", []), {"temperature", "top_p"})


def test_bootstrap_reject_policy_raises_client_error(tmp_path: Path, monkeypatch):
    # Policy that rejects temperature for nano models
    policy_file = write_yaml(
        tmp_path / "config" / "providers" / "openai.yaml",
        """
        rules:
          - when_model_matches: "^gpt-5-nano"
            action: reject
            params: [temperature]
            message: "Remove temperature for nano models."
        """,
    )

    cfg_file = write_yaml(
        tmp_path / "config" / "default.yaml",
        _build_cfg_yaml(policy_file, {"temperature": 0.2}, stream=False),
    )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: FakeAdapter))

    from pai.bootstrap import build_app
    # We only care that it’s a non-retryable client error; don’t pin the exact message
    try:
        build_app(cfg_file)
        raise AssertionError("Expected ProviderClientError due to reject policy")
    except ProviderClientError:
        pass
