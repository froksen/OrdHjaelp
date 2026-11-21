import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp import config as config_mod  # noqa: E402
from ordhjaelp.config import Config  # noqa: E402
from ordhjaelp.ui.settings import SettingsDialog, SettingsHooks, needs_restart  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeAutostart:
    def __init__(self, enabled=False):
        self.enabled = enabled

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, enabled):
        self.enabled = enabled


@pytest.fixture
def hooks(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "config_dir", lambda: tmp_path)
    calls = {"speed": [], "said": [], "clip": [], "icons": [], "restart": 0}
    h = SettingsHooks(
        config=Config(),
        set_speed=calls["speed"].append,
        say=calls["said"].append,
        set_clipboard_fallback=calls["clip"].append,
        set_icon_visible=lambda n, v: calls["icons"].append((n, v)),
        restart=lambda: calls.__setitem__("restart", calls["restart"] + 1),
        autostart=FakeAutostart(),
    )
    return h, calls, tmp_path


def test_save_applies_live_without_restart(app, hooks) -> None:
    h, calls, tmp = hooks
    d = SettingsDialog(h)
    d.speed.setValue(80)
    d.clipboard.setChecked(True)
    d.icon_screen.setChecked(False)
    d.autostart.setChecked(True)
    d.read_sentence.setChecked(True)
    d.accept()
    saved = Config.from_toml((tmp / "config.toml").read_text())
    assert saved.speed == 0.8 and saved.use_clipboard_fallback
    assert saved.show_icons["skaerm"] is False
    assert calls["clip"] == [True]
    assert ("skaerm", False) in calls["icons"]
    assert h.autostart.enabled is True
    assert calls["restart"] == 0
    assert h.config.speed == 0.8  # det kørende program kender de nye værdier
    assert h.config.read_sentence_on_period is True  # virker med det samme
    assert saved.read_sentence_on_period and not saved.read_word_on_space


def test_changing_model_restarts(app, hooks) -> None:
    h, calls, _ = hooks
    d = SettingsDialog(h)
    d.model.setCurrentIndex(d.model.findData("dansk-turbo"))
    d.accept()
    assert calls["restart"] == 1


def test_cancel_restores_speed(app, hooks) -> None:
    h, calls, tmp = hooks
    d = SettingsDialog(h)
    d.speed.setValue(130)
    assert calls["speed"][-1] == 1.3  # forhåndsvisning
    d.reject()
    assert calls["speed"][-1] == 1.0
    assert not (tmp / "config.toml").exists()


def test_needs_restart() -> None:
    a = Config()
    assert not needs_restart(a, Config(speed=1.2))
    assert needs_restart(a, Config(dictation_enabled=False))
    assert needs_restart(a, Config(dictation_model="turbo"))
    assert needs_restart(a, Config(prediction_enabled=False))


def test_read_on_select_applies_live(app, hooks) -> None:
    h, calls, tmp = hooks
    seen: list[bool] = []
    h.set_read_on_select = seen.append
    d = SettingsDialog(h)
    assert d.read_on_select.isChecked() is False  # slået fra som standard
    d.read_on_select.setChecked(True)
    d.accept()
    assert seen == [True]
    assert calls["restart"] == 0
    assert Config.from_toml((tmp / "config.toml").read_text()).read_on_select is True


def test_read_at_pointer_needs_restart() -> None:
    assert needs_restart(Config(), Config(read_at_pointer=True))


def test_read_at_pointer_checkbox_saves(app, hooks) -> None:
    h, calls, tmp = hooks
    d = SettingsDialog(h)
    assert d.read_at_pointer.isChecked() is False  # slået fra som standard
    d.read_at_pointer.setChecked(True)
    d.accept()
    assert Config.from_toml((tmp / "config.toml").read_text()).read_at_pointer is True
    assert calls["restart"] == 1  # genvejene registreres ved start


def test_pdf_ocr_applies_live(app, hooks) -> None:
    h, calls, tmp = hooks
    seen: list[bool] = []
    h.set_pdf_ocr = seen.append
    d = SettingsDialog(h)
    assert d.pdf_ocr.isChecked() is False  # slået fra som standard
    d.pdf_ocr.setChecked(True)
    d.accept()
    assert seen == [True]  # menupunktet vises med det samme
    assert calls["restart"] == 0
    assert Config.from_toml((tmp / "config.toml").read_text()).pdf_ocr_enabled is True


class _ReadySetup:
    """Opsætningen til ordforslag er i orden, så statuslinjen vises."""

    def checks(self):
        from ordhjaelp.platform.base import SetupCheck

        return [SetupCheck("IBus", True, "")]

    def guide(self):
        return []

    def open_settings(self):
        return False


@pytest.mark.parametrize("typing", [False, True])
@pytest.mark.parametrize("small", [False, True])
def test_no_label_is_clipped(app, hooks, small: bool, typing: bool) -> None:
    """Al tekst skal kunne ses helt, også på en lille skærm (så skal der rulles).

    Før blev en hjælpetekst klippet over, og "Talegenkendelse:" forsvandt, når vinduet
    ikke kunne være på skærmen.
    """
    from PySide6.QtWidgets import QLabel

    h, _calls, _tmp = hooks
    if typing:
        h.typing_setup = _ReadySetup()
        h.config.prediction_enabled = True
    d = SettingsDialog(h)
    d.show()
    if small:
        d.resize(d.width(), 300)  # meget lavere end indholdet
    app.processEvents()
    try:
        assert d.width() >= d.minimumSizeHint().width()
        # Kun rullebjælke, når der ikke er plads. Om indholdet kan være på testskærmen
        # (800 px) afhænger af skrifttypen: Noto Sans på Fedora er højere end Ubuntus.
        no_room = d._scroll.viewport().height() < d._content.sizeHint().height()
        assert no_room or not small
        assert d._scroll.verticalScrollBar().isVisible() == no_room
        for label in d.findChildren(QLabel):
            assert not label.wordWrap(), f"brug faste linjeskift: {label.text()!r}"
            if not label.isVisible() or not label.text():
                continue
            if label.wordWrap():
                needed = label.heightForWidth(label.width())
            else:
                needed = label.sizeHint().height()
                assert label.width() >= label.sizeHint().width(), label.text()
            assert label.height() >= needed, f"klippet: {label.text()!r}"
    finally:
        d.close()
