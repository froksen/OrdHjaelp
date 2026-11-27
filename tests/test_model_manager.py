import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ordhjaelp import config as config_mod  # noqa: E402
from ordhjaelp.config import Config  # noqa: E402
from ordhjaelp.models.catalog import CATALOG, Kind, get, of_kind  # noqa: E402
from ordhjaelp.ui import model_manager, tray_help  # noqa: E402
from ordhjaelp.ui.model_manager import (  # noqa: E402
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


def test_needs_first_run_follows_usage() -> None:
    from ordhjaelp.config import MESSAGES_SCREEN, USAGE_DICTATION, USAGE_READ

    cfg = Config(usage=USAGE_READ)  # kun læs op: talegenkendelse er ikke nødvendig
    assert not needs_first_run(FakeStore({VOICE.id}), cfg)
    cfg = Config(usage=USAGE_DICTATION, messages=MESSAGES_SCREEN)  # stemmen er ikke nødvendig
    assert not needs_first_run(FakeStore({"dansk-hurtig"}), cfg)
    cfg.messages = "oplaes"  # beskeder læses op: så skal stemmen hentes
    assert needs_first_run(FakeStore({"dansk-hurtig"}), cfg)


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
