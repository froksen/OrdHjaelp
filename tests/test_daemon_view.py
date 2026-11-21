"""Knaplinjen behøver ikke et område til ikoner ved uret (fx GNOME uden udvidelse)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace  # noqa: E402

from ordhjaelp import daemon  # noqa: E402
from ordhjaelp.config import VIEW_TOOLBAR, VIEW_TRAY, Config  # noqa: E402
from ordhjaelp.ui import tray as tray_mod  # noqa: E402


class FakeTrayApp:
    started = 0
    tray_area = False

    def __init__(self, *args) -> None:
        pass

    @staticmethod
    def available() -> bool:
        return FakeTrayApp.tray_area

    def run(self) -> int:
        FakeTrayApp.started += 1
        return 0


def _run(monkeypatch, view: str) -> tuple[bool, list]:
    FakeTrayApp.started = 0
    explained = []
    monkeypatch.setattr(tray_mod, "TrayApp", FakeTrayApp)
    monkeypatch.setattr(daemon, "_explain_missing_tray", lambda *a: explained.append(a) or False)
    cfg = Config()
    cfg.view = view
    ok = daemon._run_tray(None, None, None, {}, SimpleNamespace(config=cfg))
    return ok, explained


def test_toolbar_starts_without_tray_area(monkeypatch) -> None:
    ok, explained = _run(monkeypatch, VIEW_TOOLBAR)
    assert ok and FakeTrayApp.started == 1 and explained == []


def test_tray_view_explains_missing_tray_area(monkeypatch) -> None:
    ok, explained = _run(monkeypatch, VIEW_TRAY)
    assert not ok and FakeTrayApp.started == 0 and len(explained) == 1
