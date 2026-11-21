import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ordhjaelp import config as config_mod  # noqa: E402
from ordhjaelp.config import Config  # noqa: E402
from ordhjaelp.models.catalog import CATALOG, Kind, get, of_kind  # noqa: E402
from ordhjaelp.ui import model_manager, tray_help  # noqa: E402
from ordhjaelp.ui.model_manager import (  # noqa: E402
    FirstRunDialog,
    ModelManagerDialog,
    needs_first_run,
)


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
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)


class FakeStore:
    def __init__(self, installed=(), fail=()):
        self.installed = set(installed)
        self.fail = set(fail)
        self.downloaded: list[str] = []
        self.deleted: list[str] = []

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

    def delete(self, model):
        self.installed.discard(model.id)
        self.deleted.append(model.id)


def wait_until(predicate, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


VOICE = of_kind(Kind.VOICE)[0]


def test_needs_first_run() -> None:
    cfg = Config()
    assert needs_first_run(FakeStore(), cfg)
    assert needs_first_run(FakeStore({VOICE.id}), cfg)  # talemodel mangler
    assert not needs_first_run(FakeStore({VOICE.id, "dansk-hurtig"}), cfg)
    cfg.dictation_enabled = False
    assert not needs_first_run(FakeStore({VOICE.id}), cfg)


def test_first_run_preselects_recommended(app) -> None:
    dialog = FirstRunDialog(FakeStore(), Config())
    chosen = {m.id for m in dialog.chosen()}
    assert chosen == {m.id for m in CATALOG if m.recommended}
    voice_row = dialog.list.rows[VOICE.id]
    assert not voice_row.check.isEnabled()  # eneste stemme kan ikke fravælges
    assert "312 MB" in dialog.summary.text()


def test_first_run_downloads_and_saves_choice(app, tmp_path) -> None:
    store = FakeStore()
    cfg = Config()
    dialog = FirstRunDialog(store, cfg)
    dialog.list.rows["dansk-hurtig"].check.setChecked(False)
    dialog.list.rows["dansk-turbo"].check.setChecked(True)
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)
    assert store.downloaded == [VOICE.id, "dansk-turbo"]
    assert cfg.dictation_model == "dansk-turbo" and cfg.dictation_enabled
    assert Config.from_toml((tmp_path / "config.toml").read_text()).dictation_model == "dansk-turbo"


def test_first_run_without_speech_disables_dictation(app) -> None:
    cfg = Config()
    dialog = FirstRunDialog(FakeStore(), cfg)
    dialog.list.rows["dansk-hurtig"].check.setChecked(False)
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)
    assert cfg.dictation_enabled is False


def test_first_run_skips_already_installed(app) -> None:
    store = FakeStore({VOICE.id})
    dialog = FirstRunDialog(store, Config())
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)
    assert store.downloaded == ["dansk-hurtig"]


def test_first_run_failure_allows_retry(app) -> None:
    store = FakeStore(fail={"dansk-hurtig"})
    dialog = FirstRunDialog(store, Config())
    dialog._start()
    assert wait_until(lambda: dialog.start_button.text() == "Prøv igen")
    assert dialog.result() != dialog.DialogCode.Accepted
    store.fail.clear()
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)


def test_manager_download_and_delete(app) -> None:
    store = FakeStore({VOICE.id, "dansk-hurtig"})
    changes = []
    dialog = ModelManagerDialog(store, Config(), on_changed=lambda: changes.append(1))
    turbo = dialog.list.rows["dansk-turbo"]
    assert turbo.button.text() == "Hent"
    turbo.button.click()
    assert wait_until(lambda: "dansk-turbo" in store.installed and turbo.button.text() == "Slet")
    turbo.button.click()
    assert store.deleted == ["dansk-turbo"] and changes


def test_manager_protects_models_in_use(app) -> None:
    store = FakeStore({VOICE.id, "dansk-hurtig"})
    dialog = ModelManagerDialog(store, Config())
    assert not dialog.list.rows["dansk-hurtig"].button.isEnabled()
    assert not dialog.list.rows[VOICE.id].button.isEnabled()


def test_catalog_sources_are_ready_made() -> None:
    assert get("dansk-hurtig").source == "lucasw89/whisper-small-danish-ct2-int8"
    assert all(m.size_mb > 0 and m.title for m in CATALOG)
    assert model_manager.SECTION_TITLES.keys() == {Kind.VOICE, Kind.SPEECH}


# -- grundindstillinger i velkomstvinduet ----------------------------------------
class FakeAutostart:
    def __init__(self) -> None:
        self.enabled = False

    def is_enabled(self) -> bool:
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled


def test_first_run_saves_basic_settings(app, tmp_path) -> None:
    cfg = Config()
    autostart = FakeAutostart()
    dialog = FirstRunDialog(FakeStore({VOICE.id, "dansk-hurtig"}), cfg, autostart)
    basics = dialog.basics
    assert basics.autostart.isChecked()  # foreslået som standard
    basics.prediction.setChecked(False)
    basics.read_sentence.setChecked(True)
    basics.read_on_select.setChecked(True)
    basics.read_at_pointer.setChecked(True)
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)
    assert autostart.enabled
    saved = Config.from_toml((tmp_path / "config.toml").read_text("utf-8"))
    assert not saved.prediction_enabled
    assert saved.read_sentence_on_period and saved.read_on_select and saved.read_at_pointer
    assert cfg.read_at_pointer  # Ordhjælp starter med det samme med valgene


def test_first_run_without_autostart_support_hides_it(app) -> None:
    dialog = FirstRunDialog(FakeStore(), Config(), autostart=None)
    assert not dialog.basics.autostart.isVisibleTo(dialog)


@pytest.mark.skipif(sys.platform != "win32", reason="ikonerne ved uret: kun Windows")
def test_first_run_tray_icons_choice(app) -> None:
    dialog = FirstRunDialog(FakeStore({VOICE.id, "dansk-hurtig"}), Config())
    assert dialog.basics.tray_icons.isChecked()
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)
    assert tray_help.take_help_request()  # vejledningen åbnes ved start
    assert not tray_help.take_help_request()  # kun én gang
    assert not tray_help.should_show_first_run_tip()  # og ingen besked oveni

    dialog = FirstRunDialog(FakeStore({VOICE.id, "dansk-hurtig"}), Config())
    dialog.basics.tray_icons.setChecked(False)
    dialog._start()
    assert wait_until(lambda: dialog.result() == dialog.DialogCode.Accepted)
    assert not tray_help.take_help_request()


def test_first_run_fits_small_school_screen(app) -> None:
    dialog = FirstRunDialog(FakeStore(), Config(), FakeAutostart())
    # 1366x768 med 125 % skalering giver ca. 614 punkter i højden
    assert dialog.minimumSizeHint().height() <= 600
