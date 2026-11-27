"""Velkomstguiden: vælg brug, de vigtigste indstillinger og kun de nødvendige modeller."""

import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ordhjaelp import config as config_mod  # noqa: E402
from ordhjaelp.config import (  # noqa: E402
    MESSAGES_SCREEN,
    MESSAGES_SPEAK,
    USAGE_ALL,
    USAGE_DICTATION,
    USAGE_READ,
    VIEW_TRAY,
    Config,
)
from ordhjaelp.models.catalog import CATALOG, Kind, of_kind  # noqa: E402
from ordhjaelp.ui import tray_help  # noqa: E402
from ordhjaelp.ui.welcome import PAGE_MODELS, PAGE_SETTINGS, PAGE_USAGE  # noqa: E402
from ordhjaelp.ui.welcome import FirstRunDialog as Wizard  # noqa: E402

VOICE = of_kind(Kind.VOICE)[0]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(tray_help, "data_dir", lambda: tmp_path / "data")
    # Ingen rigtige beskedbokse i tests – svar altid "Ja"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)


class FakeStore:
    def __init__(self, installed=(), fail=()):
        self.installed = set(installed)
        self.fail = set(fail)
        self.downloaded: list[str] = []

    def is_installed(self, model):
        return model.id in self.installed

    def download(self, model, progress=None, cancel=None):
        if model.id in self.fail:
            raise OSError("ingen forbindelse")
        for f in (0.3, 0.7):
            if progress:
                progress(f)
        self.installed.add(model.id)
        self.downloaded.append(model.id)


class FakeAutostart:
    def __init__(self) -> None:
        self.enabled = False

    def is_enabled(self) -> bool:
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled


def wait_until(predicate, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def finish(dialog) -> None:
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)


def saved(tmp_path) -> Config:
    return Config.from_toml((tmp_path / "config.toml").read_text("utf-8"))


def go_to_models(dialog, usage: str) -> None:
    dialog.usage_buttons[usage].setChecked(True)
    dialog._next()
    assert dialog.pages.currentIndex() == PAGE_SETTINGS
    dialog._next()
    assert dialog.pages.currentIndex() == PAGE_MODELS


# -- indstillingsfilen ----------------------------------------------------------
def test_new_users_see_the_welcome_guide() -> None:
    cfg = Config.from_toml(Config().to_toml())
    assert cfg.welcome_done is False
    assert cfg.usage == USAGE_ALL and cfg.messages == MESSAGES_SPEAK


def test_old_config_without_usage_skips_the_guide() -> None:
    # Indstillinger fra før guiden: brugeren har allerede sat Ordhjælp op
    cfg = Config.from_toml("[oplaesning]\ntempo = 0.9\n")
    assert cfg.welcome_done is True and cfg.usage == USAGE_ALL


def test_usage_round_trips_and_rejects_unknown() -> None:
    cfg = Config(usage=USAGE_DICTATION, messages=MESSAGES_SCREEN, welcome_done=True)
    again = Config.from_toml(cfg.to_toml())
    assert (again.usage, again.messages, again.welcome_done) == (
        USAGE_DICTATION,
        MESSAGES_SCREEN,
        True,
    )
    odd = Config.from_toml('[brug]\nfunktioner = "alting"\nbeskeder = "brev"\n')
    assert odd.usage == USAGE_ALL and odd.messages == MESSAGES_SPEAK


def test_usage_decides_what_is_active() -> None:
    everything = dict(
        prediction_enabled=True,
        read_on_select=True,
        read_at_pointer=True,
        read_word_on_space=True,
        dictation_enabled=True,
    )
    read = Config(usage=USAGE_READ, **everything)
    assert not read.dictation_active and not read.prediction_active
    assert read.read_on_select_active and read.read_word_active and read.typing_help_enabled
    assert not read.button_allowed("dikter") and read.button_allowed("pdf")
    dictate = Config(usage=USAGE_DICTATION, **everything)
    assert dictate.dictation_active and not dictate.prediction_active
    assert not dictate.read_on_select_active and not dictate.read_at_pointer_active
    assert not dictate.typing_help_enabled
    assert dictate.button_allowed("dikter") and not dictate.button_allowed("laes")
    assert dictate.needs_voice  # beskeder læses op som standard
    dictate.messages = MESSAGES_SCREEN
    assert not dictate.needs_voice
    assert Config(**everything).prediction_active  # alle funktioner


# -- guiden -----------------------------------------------------------------------
def test_guide_starts_with_the_choice_of_usage(app) -> None:
    dialog = Wizard(FakeStore(), Config())
    assert dialog.pages.currentIndex() == PAGE_USAGE
    assert dialog.usage == USAGE_ALL  # alle funktioner er foreslået
    assert not dialog.back_button.isVisibleTo(dialog)
    assert not dialog.start_button.isVisibleTo(dialog)


def test_settings_page_shows_only_what_belongs_to_the_usage(app) -> None:
    dialog = Wizard(FakeStore(), Config())
    dialog.usage_buttons[USAGE_READ].setChecked(True)
    dialog._next()
    assert dialog.reading_box.isVisibleTo(dialog)
    assert not dialog.dictation_box.isVisibleTo(dialog)
    assert not dialog.writing_box.isVisibleTo(dialog)
    dialog.usage_buttons[USAGE_DICTATION].setChecked(True)
    assert not dialog.reading_box.isVisibleTo(dialog)
    assert dialog.dictation_box.isVisibleTo(dialog)
    dialog.usage_buttons[USAGE_ALL].setChecked(True)
    assert dialog.writing_box.isVisibleTo(dialog)


def test_all_functions_preselects_recommended(app) -> None:
    dialog = Wizard(FakeStore(), Config())
    go_to_models(dialog, USAGE_ALL)
    chosen = {m.id for m in dialog.chosen()}
    assert chosen == {m.id for m in CATALOG if m.recommended}
    assert not dialog.list.rows[VOICE.id].check.isEnabled()  # eneste stemme
    assert "312 MB" in dialog.summary.text()


def test_read_only_fetches_only_the_voice(app, tmp_path) -> None:
    store = FakeStore()
    cfg = Config()
    dialog = Wizard(store, cfg)
    go_to_models(dialog, USAGE_READ)
    assert set(dialog.list.rows) == {m.id for m in of_kind(Kind.VOICE)}
    finish(dialog)
    assert store.downloaded == [VOICE.id]
    assert saved(tmp_path).usage == USAGE_READ and saved(tmp_path).welcome_done
    assert cfg.usage == USAGE_READ  # Ordhjælp starter med det samme med valget
    assert cfg.dictation_enabled  # gemt til senere, hvis eleven vælger alle funktioner


def test_dictation_with_messages_on_screen_skips_the_voice(app, tmp_path) -> None:
    store = FakeStore()
    dialog = Wizard(store, Config())
    dialog.usage_buttons[USAGE_DICTATION].setChecked(True)
    dialog._next()
    dialog.messages_screen.setChecked(True)
    dialog._next()
    assert VOICE.id not in dialog.list.rows
    for row in dialog.list.rows.values():
        row.check.setChecked(False)
    assert not dialog.start_button.isEnabled()  # en talegenkendelse er nødvendig
    assert "talegenkendelse" in dialog.summary.text()
    dialog.list.rows["dansk-hurtig"].check.setChecked(True)
    finish(dialog)
    assert store.downloaded == ["dansk-hurtig"]
    cfg = saved(tmp_path)
    assert cfg.usage == USAGE_DICTATION and cfg.messages == MESSAGES_SCREEN
    assert cfg.dictation_active and not cfg.needs_voice


def test_dictation_suggests_messages_on_screen(app) -> None:
    dialog = Wizard(FakeStore(), Config())
    dialog.usage_buttons[USAGE_DICTATION].setChecked(True)
    assert dialog.messages_screen.isChecked()  # så stemmen ikke skal hentes
    dialog.usage_buttons[USAGE_ALL].setChecked(True)
    assert dialog.messages_speak.isChecked()  # stemmen er der alligevel
    dialog.messages_screen.click()  # elevens eget valg bliver stående
    dialog.usage_buttons[USAGE_READ].setChecked(True)
    dialog.usage_buttons[USAGE_DICTATION].setChecked(True)
    assert dialog.messages_screen.isChecked()


def test_dictation_with_spoken_messages_needs_the_voice(app) -> None:
    dialog = Wizard(FakeStore(), Config())
    dialog.usage_buttons[USAGE_DICTATION].setChecked(True)
    dialog._next()
    dialog.messages_speak.click()
    dialog._next()
    assert dialog.list.rows[VOICE.id].check.isChecked()
    assert not dialog.list.rows[VOICE.id].check.isEnabled()  # påkrævet


def test_back_and_change_rebuilds_the_list(app) -> None:
    dialog = Wizard(FakeStore(), Config())
    go_to_models(dialog, USAGE_READ)
    assert "dansk-hurtig" not in dialog.list.rows
    dialog._back()
    dialog._back()
    go_to_models(dialog, USAGE_ALL)
    assert "dansk-hurtig" in dialog.list.rows


def test_guide_downloads_and_saves_speech_choice(app, tmp_path) -> None:
    store = FakeStore()
    cfg = Config()
    dialog = Wizard(store, cfg)
    go_to_models(dialog, USAGE_ALL)
    dialog.list.rows["dansk-hurtig"].check.setChecked(False)
    dialog.list.rows["dansk-turbo"].check.setChecked(True)
    finish(dialog)
    assert store.downloaded == [VOICE.id, "dansk-turbo"]
    assert cfg.dictation_model == "dansk-turbo" and cfg.dictation_enabled
    assert saved(tmp_path).dictation_model == "dansk-turbo"


def test_all_functions_without_speech_disables_dictation(app) -> None:
    cfg = Config()
    dialog = Wizard(FakeStore(), cfg)
    go_to_models(dialog, USAGE_ALL)
    dialog.list.rows["dansk-hurtig"].check.setChecked(False)
    finish(dialog)
    assert cfg.dictation_enabled is False


def test_guide_skips_already_installed(app) -> None:
    store = FakeStore({VOICE.id})
    dialog = Wizard(store, Config())
    finish(dialog)  # "Hent og start" direkte: alle funktioner
    assert store.downloaded == ["dansk-hurtig"]


def test_guide_failure_allows_retry(app) -> None:
    store = FakeStore(fail={"dansk-hurtig"})
    dialog = Wizard(store, Config())
    dialog._start()
    assert wait_until(lambda: dialog.start_button.text() == "Prøv igen")
    assert dialog.result() != dialog.DialogCode.Accepted
    store.fail.clear()
    finish(dialog)


def test_guide_saves_settings(app, tmp_path) -> None:
    cfg = Config()
    autostart = FakeAutostart()
    dialog = Wizard(FakeStore({VOICE.id, "dansk-hurtig"}), cfg, autostart)
    assert dialog.autostart.isChecked()  # foreslået som standard
    dialog.prediction.setChecked(False)
    dialog.read_sentence.setChecked(True)
    dialog.read_on_select.setChecked(True)
    dialog.read_at_pointer.setChecked(True)
    dialog.speed.setValue(80)
    dialog.view_tray.setChecked(True)
    finish(dialog)
    assert autostart.enabled
    cfg_saved = saved(tmp_path)
    assert not cfg_saved.prediction_enabled and cfg_saved.speed == 0.8
    assert cfg_saved.read_sentence_on_period and cfg_saved.read_on_select
    assert cfg_saved.read_at_pointer and cfg_saved.view == VIEW_TRAY
    assert cfg.read_at_pointer  # Ordhjælp starter med det samme med valgene


def test_guide_without_autostart_support_hides_it(app) -> None:
    dialog = Wizard(FakeStore(), Config(), autostart=None)
    assert not dialog.autostart.isVisibleTo(dialog)


def test_models_only_after_changing_usage(app, tmp_path) -> None:
    # Eleven skiftede fra kun læs op til alle funktioner: kun talegenkendelsen mangler
    cfg = Config(usage=USAGE_ALL, welcome_done=True, speed=1.2)
    store = FakeStore({VOICE.id})
    dialog = Wizard(store, cfg, FakeAutostart(), models_only=True)
    assert dialog.pages.currentIndex() == PAGE_MODELS
    assert not dialog.back_button.isVisibleTo(dialog)
    assert "mangler" in dialog.models_intro.text()
    finish(dialog)
    assert store.downloaded == ["dansk-hurtig"]
    assert saved(tmp_path).speed == 1.2  # de andre indstillinger er urørte


@pytest.mark.parametrize("page", [PAGE_USAGE, PAGE_SETTINGS, PAGE_MODELS])
def test_guide_fits_small_school_screen(app, page) -> None:
    dialog = Wizard(FakeStore(), Config(), FakeAutostart())
    dialog._show_page(page)
    # 1366x768 med 125 % skalering giver ca. 614 punkter i højden
    assert dialog.minimumSizeHint().height() <= 600


@pytest.mark.skipif(sys.platform != "win32", reason="ikonerne ved uret: kun Windows")
def test_tray_icon_help_only_with_icons_by_the_clock(app) -> None:
    dialog = Wizard(FakeStore({VOICE.id, "dansk-hurtig"}), Config())
    dialog._next()
    assert not dialog.tray_icons.isVisibleTo(dialog)  # knaplinjen er standard
    dialog.view_tray.setChecked(True)
    assert dialog.tray_icons.isVisibleTo(dialog) and dialog.tray_icons.isChecked()
    finish(dialog)
    assert tray_help.take_help_request()  # vejledningen åbnes ved start
    assert not tray_help.take_help_request()  # kun én gang

    dialog = Wizard(FakeStore({VOICE.id, "dansk-hurtig"}), Config())
    finish(dialog)  # med knaplinjen er der ikke noget at vise
    assert not tray_help.take_help_request()


@pytest.mark.skipif(sys.platform != "win32", reason="ikonerne ved uret: kun Windows")
def test_guide_shows_how_to_show_tray_icons(app, monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(tray_help.TrayIconsHelpDialog, "exec", lambda self: opened.append(self))
    dialog = Wizard(FakeStore(), Config())
    dialog.view_tray.setChecked(True)
    dialog.tray_icons_how.click()
    assert len(opened) == 1
