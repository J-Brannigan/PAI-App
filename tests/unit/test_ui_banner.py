# tests/unit/test_ui_banner.py

from __future__ import annotations
import sys
from pathlib import Path
from copy import deepcopy
import pytest

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pai.ui.banner as banner  # import the module to monkeypatch


MIN_UI = {
    "banner": {
        "enabled": True,
        "title": "PAI",
        "subtitle": "LLM-driven CLI",
        "show_version": True,
        "watch_resize": False,
        "clear_screen": False,
        "full_width": True,
        "border_style": "cyan",
        "padding": {"top": 0, "right": 1, "bottom": 0, "left": 1},
        "fonts": [{"max_width": 9999, "name": "Standard"}],
        "align": "center",
    }
}


def test_banner_fallback_print(capsys, monkeypatch):
    # Force fallback path (no rich/pyfiglet)
    monkeypatch.setattr(banner, "HAVE_RICH", False, raising=True)
    monkeypatch.setattr(banner, "HAVE_PYFIGLET", False, raising=True)

    cfg = deepcopy(MIN_UI)
    banner.render_banner_from_config(cfg, app_version="v0.1")

    out = capsys.readouterr().out
    assert "PAI v0.1" in out
    assert "LLM-driven CLI" in out


def test_banner_rich_no_clear(monkeypatch):
    # Enable rich path
    monkeypatch.setattr(banner, "HAVE_RICH", True, raising=True)
    monkeypatch.setattr(banner, "HAVE_PYFIGLET", True, raising=True)

    # Deterministic figlet output
    monkeypatch.setattr(
        banner,
        "figlet_format",
        lambda title, font=None: f"ART:{title}:{font}",
        raising=True,
    )

    # Fake Align + Panel
    class FakeAlign:
        @staticmethod
        def center(x): return f"<CENTER>{x}"

    class FakePanel:
        def __init__(self, content, **_): self.content = content
        def __repr__(self): return f"PANEL[{self.content}]"

    monkeypatch.setattr(banner, "Align", FakeAlign, raising=True)
    monkeypatch.setattr(banner, "Panel", FakePanel, raising=True)

    # Fake console
    class FakeConsole:
        width = 80
        def __init__(self): self.cleared = False; self.printed = []
        def clear(self): self.cleared = True
        def print(self, obj): self.printed.append(repr(obj))

    fake_console = FakeConsole()
    monkeypatch.setattr(banner, "_console", fake_console, raising=True)

    cfg = deepcopy(MIN_UI)
    cfg["banner"]["clear_screen"] = False
    banner.render_banner_from_config(cfg, app_version="v0.1")

    # Should NOT clear, should print a centred panel once
    assert fake_console.cleared is False
    assert any("PANEL[<CENTER>ART:PAI:Standard]" in s for s in fake_console.printed)


def test_banner_rich_with_clear(monkeypatch):
    # Enable rich path
    monkeypatch.setattr(banner, "HAVE_RICH", True, raising=True)
    monkeypatch.setattr(banner, "HAVE_PYFIGLET", True, raising=True)
    monkeypatch.setattr(banner, "figlet_format", lambda t, font=None: f"ART:{t}:{font}", raising=True)

    class FakeAlign:
        @staticmethod
        def center(x): return f"<CENTER>{x}"

    class FakePanel:
        def __init__(self, content, **_): self.content = content
        def __repr__(self): return f"PANEL[{self.content}]"

    monkeypatch.setattr(banner, "Align", FakeAlign, raising=True)
    monkeypatch.setattr(banner, "Panel", FakePanel, raising=True)

    class FakeConsole:
        width = 120
        def __init__(self): self.cleared = False; self.printed = []
        def clear(self): self.cleared = True
        def print(self, obj): self.printed.append(repr(obj))

    fake_console = FakeConsole()
    monkeypatch.setattr(banner, "_console", fake_console, raising=True)

    cfg = deepcopy(MIN_UI)
    cfg["banner"]["clear_screen"] = True
    banner.render_banner_from_config(cfg, app_version="v0.1")

    assert fake_console.cleared is True
    assert any("PANEL[<CENTER>ART:PAI:Standard]" in s for s in fake_console.printed)


def test_banner_font_selection(monkeypatch):
    # Capture the font chosen
    chosen = {"font": None}

    monkeypatch.setattr(banner, "HAVE_RICH", True, raising=True)
    monkeypatch.setattr(banner, "HAVE_PYFIGLET", True, raising=True)

    def fake_figlet(title, font=None):
        chosen["font"] = font
        return "ART"

    monkeypatch.setattr(banner, "figlet_format", fake_figlet, raising=True)

    class FakeAlign:
        @staticmethod
        def center(x): return x

    class FakePanel:
        def __init__(self, content, **_): self.content = content
        def __repr__(self): return f"PANEL[{self.content}]"

    monkeypatch.setattr(banner, "Align", FakeAlign, raising=True)
    monkeypatch.setattr(banner, "Panel", FakePanel, raising=True)

    class FakeConsole:
        width = 35  # triggers "small" in our rules below
        def __init__(self): self.printed = []
        def clear(self): pass
        def print(self, obj): self.printed.append(repr(obj))

    fake_console = FakeConsole()
    monkeypatch.setattr(banner, "_console", fake_console, raising=True)

    cfg = deepcopy(MIN_UI)
    cfg["banner"]["fonts"] = [
        {"max_width": 39, "name": "small"},
        {"max_width": 79, "name": "Standard"},
        {"max_width": 9999, "name": "Slant"},
    ]
    banner.render_banner_from_config(cfg, app_version=None)

    assert chosen["font"] == "small"


def test_banner_align_left_does_not_call_center(monkeypatch):
    monkeypatch.setattr(banner, "HAVE_RICH", True, raising=True)
    monkeypatch.setattr(banner, "HAVE_PYFIGLET", True, raising=True)
    monkeypatch.setattr(banner, "figlet_format", lambda t, font=None: "ART", raising=True)

    called = {"center": False}

    class FakeAlign:
        @staticmethod
        def center(x):
            called["center"] = True
            return f"<CENTER>{x}"

    class FakePanel:
        def __init__(self, content, **_): self.content = content
        def __repr__(self): return f"PANEL[{self.content}]"

    class FakeConsole:
        width = 80
        def __init__(self): self.printed = []
        def clear(self): pass
        def print(self, obj): self.printed.append(repr(obj))

    monkeypatch.setattr(banner, "Align", FakeAlign, raising=True)
    monkeypatch.setattr(banner, "Panel", FakePanel, raising=True)
    monkeypatch.setattr(banner, "_console", FakeConsole(), raising=True)

    cfg = deepcopy(MIN_UI)
    cfg["banner"]["align"] = "left"
    banner.render_banner_from_config(cfg, app_version=None)

    # Ensure Align.center wasn't invoked and raw ART content reached Panel
    assert called["center"] is False
    assert any("PANEL[ART]" in s for s in banner._console.printed)


def test_banner_watch_resize_hooks_signal(monkeypatch):
    # Provide a fake signal module with SIGWINCH and a recorder
    class FakeSignalModule:
        def __init__(self):
            self.SIGWINCH = object()
            self.calls = []
        def signal(self, sig, handler):
            self.calls.append((sig, handler))

    fake_signal = FakeSignalModule()

    # Enable rich path with minimal fakes
    monkeypatch.setattr(banner, "HAVE_RICH", True, raising=True)
    monkeypatch.setattr(banner, "HAVE_PYFIGLET", True, raising=True)
    monkeypatch.setattr(banner, "figlet_format", lambda t, font=None: "ART", raising=True)

    class FakeAlign:
        @staticmethod
        def center(x): return x

    class FakePanel:
        def __init__(self, content, **_): self.content = content
        def __repr__(self): return f"PANEL[{self.content}]"

    class FakeConsole:
        width = 100
        def __init__(self): self.printed = []
        def clear(self): pass
        def print(self, obj): self.printed.append(repr(obj))

    monkeypatch.setattr(banner, "Align", FakeAlign, raising=True)
    monkeypatch.setattr(banner, "Panel", FakePanel, raising=True)
    monkeypatch.setattr(banner, "_console", FakeConsole(), raising=True)
    monkeypatch.setattr(banner, "signal", fake_signal, raising=True)

    cfg = deepcopy(MIN_UI)
    cfg["banner"]["watch_resize"] = True
    banner.render_banner_from_config(cfg, app_version=None)

    assert len(fake_signal.calls) == 1
    sig, handler = fake_signal.calls[0]
    assert sig is fake_signal.SIGWINCH
    assert callable(handler)


def test_banner_raises_when_no_matching_font(monkeypatch):
    monkeypatch.setattr(banner, "HAVE_RICH", True, raising=True)
    monkeypatch.setattr(banner, "HAVE_PYFIGLET", True, raising=True)
    monkeypatch.setattr(banner, "figlet_format", lambda t, font=None: "ART", raising=True)

    class FakeAlign:
        @staticmethod
        def center(x): return x

    class FakePanel:
        def __init__(self, content, **_): self.content = content
        def __repr__(self): return f"PANEL[{self.content}]"

    class FakeConsole:
        width = 200  # wider than any rule below

        def __init__(self): self.printed = []
        def clear(self): pass
        def print(self, obj): self.printed.append(repr(obj))

    monkeypatch.setattr(banner, "Align", FakeAlign, raising=True)
    monkeypatch.setattr(banner, "Panel", FakePanel, raising=True)
    monkeypatch.setattr(banner, "_console", FakeConsole(), raising=True)

    cfg = deepcopy(MIN_UI)
    cfg["banner"]["fonts"] = [{"max_width": 50, "name": "tiny"}]  # no catch-all
    with pytest.raises(ValueError):
        banner.render_banner_from_config(cfg, app_version=None)
