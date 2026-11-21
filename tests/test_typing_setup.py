"""Opsætningstjek til ordforslag og læs mens du skriver (IBus)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp import config as config_mod  # noqa: E402
from ordhjaelp.config import Config  # noqa: E402
from ordhjaelp.platform.base import SetupCheck  # noqa: E402
from ordhjaelp.ui.settings import SettingsDialog, SettingsHooks, needs_restart  # noqa: E402
from ordhjaelp.ui.typing_setup import TypingSetupDialog, checks_html  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeSetup:
    def __init__(self, oks: list[bool]) -> None:
        self.oks = oks
        self.opened = 0

    def checks(self) -> list[SetupCheck]:
        return [SetupCheck(f"punkt {i}", ok, f"ret {i}") for i, ok in enumerate(self.oks)]

    def guide(self) -> list[str]:
        return ["Gør dit", "Gør dat"]

    def open_settings(self) -> bool:
        self.opened += 1
        return True


def _dialog(tmp_path, monkeypatch, setup, **cfg) -> SettingsDialog:  # noqa: ANN001
    monkeypatch.setattr(config_mod, "config_dir", lambda: tmp_path)
    hooks = SettingsHooks(
        config=Config(**cfg),
        set_speed=lambda s: None,
        say=lambda t: None,
        set_clipboard_fallback=lambda b: None,
        set_icon_visible=lambda n, v: None,
        restart=lambda: None,
        typing_setup=setup,
    )
    return SettingsDialog(hooks)


def test_typing_help_covers_prediction_and_reading_while_typing() -> None:
    off = Config(prediction_enabled=False)
    assert not off.typing_help_enabled
    assert Config(prediction_enabled=False, read_sentence_on_period=True).typing_help_enabled
    assert Config(prediction_enabled=False, read_word_on_space=True).typing_help_enabled
    # Læs ved punktum uden ordforslag kræver, at IBus kobles på -> genstart
    assert needs_restart(off, Config(prediction_enabled=False, read_sentence_on_period=True))


def test_status_shown_only_when_a_typing_option_is_chosen(app, tmp_path, monkeypatch) -> None:
    d = _dialog(tmp_path, monkeypatch, FakeSetup([False, False]), prediction_enabled=False)
    assert d._typing_row.isHidden()
    d.read_sentence.setChecked(True)
    assert not d._typing_row.isHidden()
    assert "Mangler" in d.typing_status.text()


def test_status_ok_when_everything_is_set_up(app, tmp_path, monkeypatch) -> None:
    d = _dialog(tmp_path, monkeypatch, FakeSetup([True, True, True]))
    assert "Klar" in d.typing_status.text()


def test_only_connection_missing_before_save_is_ok(app, tmp_path, monkeypatch) -> None:
    # IBus er sat op, men Ordhjælp kobler sig først på, når indstillingen gemmes
    d = _dialog(tmp_path, monkeypatch, FakeSetup([True, True, False]), prediction_enabled=False)
    d.prediction.setChecked(True)
    assert "når du gemmer" in d.typing_status.text()


def test_no_setup_on_other_platforms(app, tmp_path, monkeypatch) -> None:
    d = _dialog(tmp_path, monkeypatch, None)
    assert not hasattr(d, "typing_status")


def test_checks_html_shows_only_first_fix() -> None:
    html = checks_html(
        [
            SetupCheck("a", True, "ret a"),
            SetupCheck("b", False, "ret b"),
            SetupCheck("c", False, "ret c"),
        ]
    )
    assert "ret b" in html
    assert "ret a" not in html and "ret c" not in html


def test_guide_dialog_rechecks_and_opens_settings(app) -> None:
    setup = FakeSetup([False])
    dialog = TypingSetupDialog(setup)
    assert "✘" in dialog.status.text()
    setup.oks = [True]
    dialog.refresh()
    assert "✔" in dialog.status.text()
    dialog._open_settings()
    assert setup.opened == 1
