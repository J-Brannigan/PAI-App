from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from .config_loader import load_config
from .providers.registry import ProviderRegistry
from .storage.transcript import Transcript
from .resilience.resilient_provider import ResilientProvider, ResiliencePolicy
from .secrets.sources import SecretsResolver


def build_app(config_path: Path, repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Composition root: load YAML, build provider (wrapped with resilience), and create Transcript.
    Returns: dict with cfg, paths, provider, transcript.
    """
    load_dotenv()
    cfg = load_config(config_path)
    config_dir = config_path.resolve().parent
    repo_root = repo_root or Path(__file__).resolve().parents[2]

    # ----- Providers -----
    ProviderRegistry.ensure_imports()  # make sure built-ins register

    provider_name = cfg["model"]["provider"]
    model_name = cfg["model"]["name"]
    provider_cfg = (cfg.get("providers") or {}).get(provider_name, {})

    secrets_cfg = cfg.get("secrets") or {}
    method = secrets_cfg.get("method","env")
    mapping = secrets_cfg.get("mapping", {})
    resolver = SecretsResolver(method=method, mapping=mapping)

    adapter_cls = ProviderRegistry.get(provider_name)
    inner = adapter_cls.create(model_name=model_name, provider_cfg=provider_cfg, secrets=resolver)

    policy = ResiliencePolicy()  # tweak later or make YAML-driven
    provider = ResilientProvider(inner, policy=policy)

    # ----- Transcript path -----
    tdir_raw = cfg["storage"]["transcripts_dir"]
    tdir_path = Path(tdir_raw)
    transcripts_dir = (repo_root / tdir_path).resolve() if not tdir_path.is_absolute() else tdir_path

    # ----- System prompt -----
    prompts_dir = Path(__file__).resolve().parent / "prompts"
    sys_prompt_path = prompts_dir / "system.txt"
    system_prompt = sys_prompt_path.read_text(encoding="utf-8") if sys_prompt_path.exists() else "You're a helpful AI."

    # ----- Transcript object -----
    backend = cfg["storage"]["backend"]
    resume_id = cfg["storage"].get("resume")
    transcript = Transcript(
        system_prompt=system_prompt,
        session_id=resume_id,
        root_dir=(transcripts_dir if backend == "file" else None),
        header_meta={"config_path": str(config_path), "provider": provider_name, "model": model_name},
    )

    return {
        "cfg": cfg,
        "paths": {"config_dir": config_dir, "repo_root": repo_root, "transcripts_dir": transcripts_dir},
        "provider": provider,
        "transcript": transcript,
    }