from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import yaml

class UIConfigError(ValueError):
    pass

def _get(d: Dict[str, Any], dotted: str) -> Any:
    cur: Any = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            raise UIConfigError(f"Missing UI key '{dotted}'")
        cur = cur[k]
    return cur

def load_ui_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise UIConfigError(f"UI config not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    # Required keys (no defaults in code)
    required = [
        "banner.enabled",
        "banner.title",
        "banner.show_version",
        "banner.watch_resize",
        "banner.clear_screen",
        "banner.full_width",
        "banner.border_style",
        "banner.padding.top",
        "banner.padding.right",
        "banner.padding.bottom",
        "banner.padding.left",
        "banner.fonts",
        "banner.align",
    ]
    for key in required:
        _get(raw, key)

    # Basic shape check for fonts
    fonts = _get(raw, "banner.fonts")
    if not isinstance(fonts, list) or not all(isinstance(i, dict) and "max_width" in i and "name" in i for i in fonts):
        raise UIConfigError("banner.fonts must be a list of {max_width:int, name:str}")

    return raw
