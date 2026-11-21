"""Knaplinjen behøver ikke et område til ikoner ved uret."""

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


def _run(monkeypatch, view: str) -> tuple[bool, Config]:
    FakeTrayApp.started = 0
    monkeypatch.setattr(tray_mod, "TrayApp", FakeTrayApp)
    cfg = Config()
    cfg.view = view
    ok = daemon._run_tray(None, None, None, {}, SimpleNamespace(config=cfg))
    return ok, cfg


def test_toolbar_starts_without_tray_area(monkeypatch) -> None:
    ok, cfg = _run(monkeypatch, VIEW_TOOLBAR)
    assert ok and FakeTrayApp.started == 1 and cfg.view == VIEW_TOOLBAR


def test_tray_view_falls_back_to_toolbar_without_tray_area(monkeypatch) -> None:
    """Kan skrivebordet ikke vise ikoner ved uret, bruges knaplinjen i stedet."""
    ok, cfg = _run(monkeypatch, VIEW_TRAY)
    assert ok and FakeTrayApp.started == 1 and cfg.view == VIEW_TOOLBAR
