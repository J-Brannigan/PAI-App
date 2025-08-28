import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

from .providers.openai import OpenAIFunctionProvider
from .providers.echo import EchoProvider
from .utils.secrets import get_openai_api_key

load_dotenv()

def load_config(path: Path) -> dict:
    if path.exists():
        return yaml.safe_load(path.read_text()) or {}
    return {}

def build_app(config_path):
    cfg = load_config(config_path)

    provider = (cfg.get("model", {}) or {}).get("provider", "openai").lower()
    model_name = (cfg.get("model", {}) or {}).get("name", "gpt-4o-mini")

    if provider == "openai":
        openai_key = get_openai_api_key()
        if openai_key:
            model = OpenAIFunctionProvider(model=model_name, api_key=openai_key)
        else:
            raise ValueError("OpenAI API key could not be found")
    elif provider == "echo":
        model = EchoProvider()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    return {
        "cfg": cfg,
        "model": model
    }
