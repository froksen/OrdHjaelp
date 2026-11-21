"""Besked, når ikonerne ved uret ikke kan vises (GNOME uden udvidelse)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from ordhjaelp.ui import tray_missing  # noqa: E402

HOTKEYS = {"laes": "CTRL+ALT+L", "dikter": "CTRL+ALT+D", "skaerm": "CTRL+ALT+B"}


class FakeExtension:
    name = "AppIndicator and KStatusNotifierItem Support"
    install_command = "sudo dnf install gnome-shell-extension-appindicator"

    def __init__(self, state: str, starts: bool = True) -> None:
        self._state = state
        self._starts = starts
        self.enable_calls = 0

    def state(self) -> str:
        return self._state

    def enable(self) -> bool:
        self.enable_calls += 1
        return True

    def wait_until_ready(self, timeout: float) -> bool:
        return self._starts


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(tray_missing, "data_dir", lambda: tmp_path)


def _text(dialog) -> str:  # noqa: ANN001
    return "\n".join(label.text() for label in dialog.findChildren(QLabel))


def test_missing_extension_explains_how_to_install(app) -> None:
    dialog = tray_missing.MissingTrayDialog(FakeExtension("mangler"), HOTKEYS)
    text = _text(dialog)
    assert "AppIndicator" in text
    assert "sudo dnf install gnome-shell-extension-appindicator" in text
    assert "Log ud" in text
    assert dialog.enable_button is None


def test_shows_shortcuts_meanwhile(app) -> None:
    text = _text(tray_missing.MissingTrayDialog(FakeExtension("mangler"), HOTKEYS))
    assert "Ctrl+Alt+L" in text and "Ctrl+Alt+D" in text and "Ctrl+Alt+B" in text
    text = _text(tray_missing.MissingTrayDialog(FakeExtension("mangler"), None))
    assert "Ctrl+Alt" not in text


def test_disabled_extension_is_enabled_by_button(app) -> None:
    ext = FakeExtension("slået fra")
    dialog = tray_missing.MissingTrayDialog(ext, HOTKEYS)
    dialog.enable_button.click()
    assert ext.enable_calls == 1
    assert dialog.enabled


def test_enabled_but_not_running_asks_to_log_in_again(app) -> None:
    dialog = tray_missing.MissingTrayDialog(FakeExtension("slået fra", starts=False), HOTKEYS)
    dialog.enable_button.click()
    assert not dialog.enabled
    assert dialog.result_label.isVisibleTo(dialog)
    assert "Log ud" in dialog.result_label.text()


def test_can_be_hidden(app) -> None:
    assert tray_missing.should_show()
    dialog = tray_missing.MissingTrayDialog(FakeExtension("mangler"))
    dialog.hide_box.setChecked(True)
    dialog.reject()
    assert not tray_missing.should_show()
    assert not tray_missing.explain_missing_tray(FakeExtension("mangler"), None)
