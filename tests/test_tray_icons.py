"""Vis ikonerne ved uret altid (Windows 11 gemmer nye ikoner under ^)."""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp import config as config_mod  # noqa: E402
from ordhjaelp.config import Config  # noqa: E402
from ordhjaelp.platform.windows.tray_icons import expand, same_file  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_always_visible_is_on_by_default_and_saved() -> None:
    assert Config().icons_always_visible is True
    cfg = Config(icons_always_visible=False)
    again = Config.from_toml(cfg.to_toml())
    assert again.icons_always_visible is False
    assert "altid_synlige" not in again.show_icons  # ikke et ikon


def test_old_settings_file_keeps_icons() -> None:
    cfg = Config.from_toml("[ikoner]\ndikter = false\n")
    assert cfg.show_icons["dikter"] is False
    assert cfg.icons_always_visible is True


def test_expand_known_folder() -> None:
    folders = {"6D809377-6AF0-444B-8957-A3773F02200E": r"C:\Program Files"}
    path = r"{6D809377-6AF0-444B-8957-A3773F02200E}\Ordhjaelp\Ordhjaelp.exe"
    assert expand(path, known_folder=folders.get) == r"C:\Program Files\Ordhjaelp\Ordhjaelp.exe"
    assert expand(r"C:\x\y.exe", known_folder=folders.get) == r"C:\x\y.exe"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-stier")
def test_same_file_ignores_case() -> None:
    assert same_file(r"C:\Python\PythonW.exe", r"c:\python\pythonw.exe")
    assert not same_file(r"C:\Python\pythonw.exe", r"C:\Python\python.exe")


def test_settings_checkbox_calls_hook_only_when_changed(app, tmp_path, monkeypatch) -> None:
    from ordhjaelp.ui.settings import SettingsDialog, SettingsHooks

    monkeypatch.setattr(config_mod, "config_dir", lambda: tmp_path)
    calls: list[bool] = []
    hooks = SettingsHooks(
        config=Config(),
        set_speed=lambda s: None,
        say=lambda t: None,
        set_clipboard_fallback=lambda b: None,
        set_icon_visible=lambda n, v: None,
        restart=lambda: None,
        set_icons_always_visible=calls.append,
    )
    dialog = SettingsDialog(hooks)
    assert dialog.icons_always.isChecked()
    assert dialog.icons_always.isVisibleTo(dialog) == (sys.platform == "win32")
    dialog.icons_always.setChecked(False)
    dialog.accept()
    assert calls == [False]
    assert (
        Config.from_toml((tmp_path / "config.toml").read_text("utf-8")).icons_always_visible
        is False
    )
