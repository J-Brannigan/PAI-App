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


def test_bootstrap_applies_drop_policy_once_and_filters_params(tmp_path: Path, monkeypatch, capsys):
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

    # Build config as a Python dict, then dump to YAML
    cfg_dict = {
        "model": {"provider": "openai", "name": "gpt-5-nano-2025-08-07"},
        "providers": {
            "openai": {
                "params": {"temperature": 0.2, "top_p": 0.9, "keep": "ok"},
                "policy_file": str(policy_file),
                "timeout": 10,
            }
        },
        "secrets": {"method": "env", "mapping": {"openai": {"api_key": "OPENAI_API_KEY"}}},
        "storage": {"backend": "file", "transcripts_dir": "sessions"},
        "runtime": {"stream": True},
    }
    cfg_yaml = yaml.safe_dump(cfg_dict, sort_keys=False)
    cfg_file = write_yaml(tmp_path / "config" / "default.yaml", cfg_yaml)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: FakeAdapter))

    from pai.bootstrap import build_app
    app = build_app(cfg_file)

    assert FakeAdapter.created is True
    assert FakeAdapter.captured_params == {"keep": "ok"}  # temperature/top_p removed
    out = capsys.readouterr().out
    assert "Nano models use default sampling only." in out


def test_bootstrap_reject_policy_raises_client_error(tmp_path: Path, monkeypatch):
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

    cfg_dict = {
        "model": {"provider": "openai", "name": "gpt-5-nano-2025-08-07"},
        "providers": {
            "openai": {
                "params": {"temperature": 0.2},
                "policy_file": str(policy_file),
            }
        },
        "secrets": {"method": "env", "mapping": {"openai": {"api_key": "OPENAI_API_KEY"}}},
        "storage": {"backend": "file", "transcripts_dir": "sessions"},
        "runtime": {"stream": False},
    }
    cfg_yaml = yaml.safe_dump(cfg_dict, sort_keys=False)
    cfg_file = write_yaml(tmp_path / "config" / "default.yaml", cfg_yaml)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(ProviderRegistry, "get", classmethod(lambda cls, name: FakeAdapter))

    from pai.bootstrap import build_app
    try:
        build_app(cfg_file)
        raise AssertionError("Expected ProviderClientError due to reject policy")
    except ProviderClientError as e:
        assert "Remove temperature for nano models." in str(e)
