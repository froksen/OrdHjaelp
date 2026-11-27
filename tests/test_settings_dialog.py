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
    d.icon_pdf.setChecked(False)
    d.autostart.setChecked(True)
    d.read_sentence.setChecked(True)
    d.accept()
    saved = Config.from_toml((tmp / "config.toml").read_text())
    assert saved.speed == 0.8 and saved.use_clipboard_fallback
    assert saved.show_icons["skaerm"] is False
    assert calls["clip"] == [True]
    assert ("skaerm", False) in calls["icons"]
    assert saved.show_icons["pdf"] is False and ("pdf", False) in calls["icons"]
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


def test_pdf_is_one_checkbox_and_applies_live(app, hooks) -> None:
    h, calls, tmp = hooks
    d = SettingsDialog(h)
    assert not hasattr(d, "pdf_ocr")  # ikke længere et ekstra flueben til menuen
    assert d.icon_pdf.isChecked()  # vist som standard
    d.icon_pdf.setChecked(False)
    d.accept()
    assert ("pdf", False) in calls["icons"]  # skjules med det samme
    assert calls["restart"] == 0
    assert Config.from_toml((tmp / "config.toml").read_text()).show_icons["pdf"] is False


class _ReadySetup:
    """Opsætningen til ordforslag er i orden, så statuslinjen vises."""

    def checks(self):
        from ordhjaelp.platform.base import SetupCheck

        return [SetupCheck("IBus", True, "")]

    def guide(self):
        return []

    def open_settings(self):
        return False


def test_settings_are_split_into_tabs(app, hooks) -> None:
    """Flere faner, så der ikke er så meget at overskue ad gangen."""
    h, _calls, _tmp = hooks
    d = SettingsDialog(h)
    titles = [d._tabs.tabText(i) for i in range(d._tabs.count())]
    assert titles == ["Brug", "Læs op", "Skriv", "Knapper", "Start og genveje"]

    def tab_of(widget):
        return next(i for i, (_, c) in enumerate(d._pages) if c.isAncestorOf(widget))

    assert tab_of(d.usage_buttons["alt"]) == tab_of(d.messages_screen) == 0
    assert tab_of(d.speed) == tab_of(d.read_at_pointer) == 1
    assert tab_of(d.dictation) == tab_of(d.prediction) == 2
    assert tab_of(d.view_toolbar) == tab_of(d.icon_pdf) == 3
    assert tab_of(d.autostart) == 4


def test_usage_hides_what_does_not_belong(app, hooks) -> None:
    h, _calls, _tmp = hooks
    d = SettingsDialog(h)
    assert d.usage == "alt" and d._tabs.isTabVisible(1)
    d.usage_buttons["diktering"].setChecked(True)
    assert not d._tabs.isTabVisible(1)  # Læs op
    assert d.dictation_box.isVisibleTo(d.dictation_box.parentWidget())
    assert not d.typing_box.isVisibleTo(d.typing_box.parentWidget())
    assert not d.icon_screen.isVisibleTo(d.icon_screen.parentWidget())
    assert d.icon_mic.isVisibleTo(d.icon_mic.parentWidget())
    assert d.messages_box.isVisibleTo(d.messages_box.parentWidget())
    d.usage_buttons["oplaesning"].setChecked(True)
    assert d._tabs.isTabVisible(1)
    assert not d.dictation_box.isVisibleTo(d.dictation_box.parentWidget())
    assert not d.prediction.isVisibleTo(d.prediction.parentWidget())
    assert d.read_word.isVisibleTo(d.read_word.parentWidget())
    assert not d.icon_mic.isVisibleTo(d.icon_mic.parentWidget())
    assert not d.messages_box.isVisibleTo(d.messages_box.parentWidget())


def test_changing_usage_saves_and_restarts(app, hooks) -> None:
    h, calls, tmp = hooks
    h.config.read_on_select = True
    d = SettingsDialog(h)
    d.usage_buttons["diktering"].setChecked(True)
    d.messages_screen.setChecked(True)
    d.accept()
    saved = Config.from_toml((tmp / "config.toml").read_text())
    assert saved.usage == "diktering" and saved.messages == "skaerm"
    assert saved.read_on_select  # fravalgt, men gemt til senere
    assert calls["restart"] == 1
    assert h.config.usage == "diktering"


def test_needs_restart_on_usage_and_voice() -> None:
    assert needs_restart(Config(), Config(usage="oplaesning"))
    # Kun diktering: skiftet fra beskeder på skærmen til oplæst kræver stemmen
    a = Config(usage="diktering", messages="skaerm")
    assert needs_restart(a, Config(usage="diktering", messages="oplaes"))
    # Med læs op er stemmen der i forvejen: beskederne skifter uden genstart
    assert not needs_restart(Config(messages="skaerm"), Config(messages="oplaes"))


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
        for index, (scroll, content) in enumerate(d._pages):
            d._tabs.setCurrentIndex(index)
            app.processEvents()
            # Kun rullebjælke, når der ikke er plads. Om indholdet kan være på testskærmen
            # (800 px) afhænger af skrifttypen: Noto Sans på Fedora er højere end Ubuntus.
            no_room = scroll.viewport().height() < content.sizeHint().height()
            assert scroll.verticalScrollBar().isVisible() == no_room
            for label in content.findChildren(QLabel):
                assert not label.wordWrap(), f"brug faste linjeskift: {label.text()!r}"
                if not label.isVisible() or not label.text():
                    continue
                assert label.width() >= label.sizeHint().width(), label.text()
                assert label.height() >= label.sizeHint().height(), f"klippet: {label.text()!r}"
        if small:  # mindst én fane er for høj til 300 punkter og skal rulles
            assert any(s.viewport().height() < c.sizeHint().height() for s, c in d._pages)
    finally:
        d.close()
