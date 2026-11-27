"""Oversigten over genveje, og at genvejene vises i menuerne."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from ordhjaelp.config import Config  # noqa: E402
from ordhjaelp.ui.shortcuts import (  # noqa: E402
    GLOBAL_SHORTCUTS,
    ShortcutsDialog,
    pretty,
    shortcut_for,
    with_shortcut,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_pretty_writes_keys_as_on_the_keyboard() -> None:
    assert pretty("CTRL+ALT+L") == "Ctrl+Alt+L"
    assert pretty("ctrl+alt+1") == "Ctrl+Alt+1"
    assert pretty("SHIFT+F5") == "Shift+F5"
    assert pretty("CTRL+SPACE") == "Ctrl+Mellemrum"


def test_menu_text_gets_shortcut_after_tab() -> None:
    keys = {"laes": "CTRL+ALT+L"}
    assert with_shortcut("Læs op", keys, "laes") == "Læs op\tCtrl+Alt+L"
    assert with_shortcut("Stop", keys, "stop") == "Stop"  # ingen genvej
    assert with_shortcut("Læs op", None, "laes") == "Læs op"  # startet uden genveje


def test_every_default_shortcut_is_explained() -> None:
    explained = {action for action, _ in GLOBAL_SHORTCUTS}
    assert set(Config().hotkeys) <= explained


def _texts(dialog) -> list[str]:  # noqa: ANN001
    return [label.text() for label in dialog.findChildren(QLabel)]


def test_dialog_lists_configured_shortcuts(app) -> None:
    cfg = Config(read_at_pointer=True)
    cfg.hotkeys["laes"] = "CTRL+SHIFT+R"  # eleven har selv ændret genvejen
    texts = _texts(ShortcutsDialog(cfg))
    assert "Ctrl+Shift+R" in texts
    assert "Ctrl+Alt+L" not in texts
    assert "F1 – F5" in texts and "Esc" in texts
    assert shortcut_for(cfg.hotkeys, "laes_ord") in texts


def test_dialog_marks_pointer_shortcuts_when_turned_off(app) -> None:
    texts = _texts(ShortcutsDialog(Config(read_at_pointer=False)))
    assert any(t.startswith("Læs ordet under musen *") for t in texts)
    assert any("Slå »Læs under musen" in t for t in texts)


def test_suggestion_popup_shows_keys(app) -> None:
    from ordhjaelp.ui.suggestions import SuggestionPopup

    popup = SuggestionPopup(lambda: None, lambda: (0, 0))
    popup._show(["skole", "skov"], -1)
    layout = popup.layout()
    assert layout.itemAt(layout.count() - 1).widget() is popup.hint  # nederst
    assert "Esc" in popup.hint.text()
    assert "Højreklik" in popup.hint.text()
    popup.hide()


def test_shortcuts_follow_usage(app) -> None:
    dictate = " ".join(_texts(ShortcutsDialog(Config(usage="diktering"))))
    assert "Ctrl+Alt+D" in dictate and "Ctrl+Alt+L" not in dictate
    read = " ".join(_texts(ShortcutsDialog(Config(usage="oplaesning"))))
    assert "Ctrl+Alt+L" in read and "Ctrl+Alt+D" not in read
