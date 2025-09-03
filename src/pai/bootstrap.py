from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from .config_loader import load_config
from .providers.registry import ProviderRegistry
from .storage.transcript import Transcript
from .resilience.resilient_provider import ResilientProvider, ResiliencePolicy
from pai.providers.param_policy import ParamPolicy
from pai.core.errors import ProviderClientError
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

    warnings=[]

    raw_params = dict(provider_cfg.get("params", {}) or {})

    # Load optional per-provider policy YAML
    policy_file = (cfg.get("providers", {})
                   .get(provider_name, {})
                   .get("policy_file"))  # allow override in YAML
    if policy_file:
        policy_path = Path(policy_file)
        if not policy_path.is_absolute():
            # resolve relative to config dir
            policy_path = config_path.parent / policy_path
    else:
        # default location: config/providers/<name>.yaml
        policy_path = (config_path.parent / "providers" / f"{provider_name}.yaml")

    effective_params = raw_params
    if policy_path.exists():
        policy = ParamPolicy.load(policy_path)
        try:
            effective_params, warns = policy.evaluate(model_name, raw_params)

            # Compute exactly what was dropped
            dropped = {k: v for k, v in (raw_params or {}).items() if k not in (effective_params or {})}

            if dropped:
                try:
                    policy_rel = str(policy_path.relative_to(config_dir))
                except Exception:
                    policy_rel = str(policy_path)
                cfg_loc = f"{config_path.name} → providers.{provider_name}.params"

                warnings.append({
                    "type": "policy_drop",
                    "provider": provider_name,
                    "model": model_name,
                    "source": cfg_loc,
                    "policy": policy_rel,
                    "dropped": dropped,  # dict of key->value
                    "message": "Model does not accept these parameters; they were dropped.",
                })
        except ValueError as e:
            # Map to neutral client error so resilience won’t retry
            raise ProviderClientError(str(e))

    Adapter = ProviderRegistry.get(provider_name)
    inner = Adapter.create(
        model_name=model_name,
        provider_cfg={**provider_cfg, "params": effective_params},
        secrets=resolver,
    )

    policy = ResiliencePolicy()
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
        "warnings": warnings
    }