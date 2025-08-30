from __future__ import annotations
import shutil, signal
from typing import Optional, Dict, Any

try:
    from pyfiglet import figlet_format
    HAVE_PYFIGLET = True
except Exception:
    HAVE_PYFIGLET = False

try:
    from rich.console import Console
    from rich.align import Align
    from rich.panel import Panel
    HAVE_RICH = True
except Exception:
    HAVE_RICH = False

_console = Console() if HAVE_RICH else None

def _pick_font(fonts_cfg, width: int) -> str:
    # first rule where width <= max_width
    for rule in fonts_cfg:
        if width <= int(rule["max_width"]):
            return str(rule["name"])
    # should not happen if config has a catch-all; raise to avoid silent defaults
    raise ValueError("No matching font rule for console width")

def render_banner_from_config(ui_cfg: Dict[str, Any], app_version: Optional[str]) -> None:
    b = ui_cfg["banner"]
    if not b["enabled"]:
        return

    if not (HAVE_RICH and HAVE_PYFIGLET):
        # Libraries required but not present; fail quiet to avoid “defaults”
        print(f"{b['title']}{' ' + app_version if app_version and b['show_version'] else ''}")
        if sub := b.get("subtitle"):
            print(sub)
        return

    def _render() -> None:
        w = _console.width
        font = _pick_font(b["fonts"], w)
        art = figlet_format(b["title"], font=font)
        art = "\n".join(line.rstrip() for line in art.splitlines())

        padding = (int(b["padding"]["top"]), int(b["padding"]["right"]),
                   int(b["padding"]["bottom"]), int(b["padding"]["left"]))
        panel = Panel(
            Align.center(art) if b["align"] == "center" else art,
            title=(app_version if b["show_version"] else None),
            subtitle=b.get("subtitle") or None,
            border_style=b["border_style"],
            expand=bool(b["full_width"]),
            padding=padding,
        )

        if b["clear_screen"]:
            _console.clear()
        _console.print(panel)

    _render()
    if b["watch_resize"] and hasattr(signal, "SIGWINCH"):
        signal.signal(signal.SIGWINCH, lambda *_: _render())
