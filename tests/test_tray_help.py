"""Vejledning i at vise ikonerne ved uret (Windows 11 gemmer dem under ^)."""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from ordhjaelp import config as config_mod  # noqa: E402
from ordhjaelp.config import VIEW_TRAY, Config  # noqa: E402
from ordhjaelp.ui import tray_help  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_old_setting_from_0_2_is_ignored() -> None:
    cfg = Config.from_toml("[ikoner]\ndikter = false\naltid_synlige = true\n")
    assert cfg.show_icons == {"dikter": False, "skaerm": True, "pdf": True}
    assert "altid_synlige" not in cfg.to_toml()


def test_first_run_tip_shown_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tray_help, "data_dir", lambda: tmp_path / "data")
    assert tray_help.should_show_first_run_tip()
    tray_help.remember_first_run_tip()
    assert not tray_help.should_show_first_run_tip()


def _button(dialog, text: str) -> QPushButton:  # noqa: ANN001
    return next(b for b in dialog.findChildren(QPushButton) if b.text() == text)


def test_dialog_opens_windows_settings(app) -> None:
    calls = []
    dialog = tray_help.TrayIconsHelpDialog(lambda: calls.append(1) or True)
    _button(dialog, "Åbn Windows' indstillinger").click()
    assert calls == [1]
    assert not dialog.open_failed.isVisibleTo(dialog)


def test_dialog_explains_when_settings_cannot_open(app) -> None:
    dialog = tray_help.TrayIconsHelpDialog(lambda: False)
    _button(dialog, "Åbn Windows' indstillinger").click()
    assert dialog.open_failed.isVisibleTo(dialog)


def test_settings_button_only_on_windows(app, tmp_path, monkeypatch) -> None:
    from ordhjaelp.ui.settings import SettingsDialog, SettingsHooks

    monkeypatch.setattr(config_mod, "config_dir", lambda: tmp_path)
    cfg = Config()
    cfg.view = VIEW_TRAY
    hooks = SettingsHooks(
        config=cfg,
        set_speed=lambda s: None,
        say=lambda t: None,
        set_clipboard_fallback=lambda b: None,
        set_icon_visible=lambda n, v: None,
        restart=lambda: None,
    )
    dialog = SettingsDialog(hooks)
    # Knappen ligger på fanen Knapper, som ikke er åben: se på knappen selv, ikke fanen
    assert (not dialog.tray_help.isHidden()) == (sys.platform == "win32")
    # Med knaplinjen er der ingen ikoner under ^ at vise frem
    dialog.view_toolbar.setChecked(True)
    assert dialog.tray_help.isHidden()
    dialog.view_tray.setChecked(True)
    assert (not dialog.tray_help.isHidden()) == (sys.platform == "win32")
