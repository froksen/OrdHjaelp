"""MSIX-pakken til Microsoft Store: manifestet, versionen og start ved login.

Det meste kan afprøves på Linux. Selve pakken bygges og installeres i CI på Windows.
"""

import importlib.util
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ordhjaelp import cli  # noqa: E402
from ordhjaelp.config import Config, default_config  # noqa: E402
from ordhjaelp.platform.windows import store  # noqa: E402
from ordhjaelp.platform.windows.store import StartupState, StoreAutostart  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NS = {
    "m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
    "uap5": "http://schemas.microsoft.com/appx/manifest/uap/windows10/5",
    "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10",
    "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
}


def _load_make_msix():
    path = ROOT / "packaging" / "windows" / "store" / "make_msix.py"
    spec = importlib.util.spec_from_file_location("make_msix", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


make_msix = _load_make_msix()


# -- version og manifest ------------------------------------------------------------
@pytest.mark.parametrize(
    ("version", "msix"),
    [("0.4.0.1", "0.4.1.0"), ("0.4.0", "0.4.0.0"), ("1.2.3.4", "1.2.304.0"), ("2", "2.0.0.0")],
)
def test_store_version_ends_with_zero(version, msix) -> None:
    assert make_msix.store_version(version) == msix


def test_store_version_keeps_order() -> None:
    order = ["0.4.0", "0.4.0.1", "0.4.0.2", "0.4.1", "0.5.0"]
    msix = [tuple(map(int, make_msix.store_version(v).split("."))) for v in order]
    assert msix == sorted(msix)


def test_store_version_rejects_what_cannot_be_kept_in_order() -> None:
    with pytest.raises(ValueError):
        make_msix.store_version("0.4.0.100")


def test_project_version_works_as_store_version() -> None:
    import tomllib

    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert make_msix.store_version(version).endswith(".0")


def _manifest(ident=None):
    ident = ident or make_msix.identity()
    return ET.fromstring(make_msix.manifest("0.4.0.1", ident))


def test_manifest_has_identity_and_version() -> None:
    ident = make_msix.identity()
    root = _manifest()
    node = root.find("m:Identity", NS)
    assert node.get("Name") == ident["navn"] and node.get("Publisher") == ident["udgiver"]
    assert node.get("Version") == "0.4.1.0"
    assert root.find("m:Properties/m:DisplayName", NS).text == ident["visningsnavn"]


def test_manifest_escapes_names() -> None:
    ident = make_msix.identity() | {"visningsnavn": 'Ord & "hjælp" <ny>'}
    root = _manifest(ident)  # ville ikke kunne læses uden escape
    assert root.find("m:Properties/m:DisplayName", NS).text == 'Ord & "hjælp" <ny>'


def test_manifest_asks_for_microphone_and_full_trust() -> None:
    root = _manifest()
    caps = root.find("m:Capabilities", NS)
    assert caps.find("rescap:Capability[@Name='runFullTrust']", NS) is not None
    assert caps.find("m:DeviceCapability[@Name='microphone']", NS) is not None


def test_manifest_startup_task_matches_the_code() -> None:
    task = _manifest().find(".//desktop:StartupTask", NS)
    assert task.get("TaskId") == store.STARTUP_TASK_ID == make_msix.STARTUP_TASK_ID
    assert task.get("Enabled") == "false"  # først når eleven slår det til


def test_manifest_has_terminal_alias() -> None:
    alias = _manifest().find(".//uap5:ExecutionAlias", NS)
    assert alias.get("Alias") == "ordhjaelp.exe"


def test_manifest_logos_are_made(tmp_path) -> None:
    from PySide6.QtGui import QImage

    root = _manifest()
    visual = root.find(".//uap:VisualElements", NS)
    wanted = {
        root.find("m:Properties/m:Logo", NS).text,
        visual.get("Square150x150Logo"),
        visual.get("Square44x44Logo"),
    }
    make_msix.make_assets(tmp_path / "Assets")
    for logo in wanted:
        file = tmp_path / logo.replace("\\", "/")
        assert file.exists(), logo
        image = QImage(str(file))
        assert image.width() == image.height() == make_msix.ASSETS[file.name]


def test_missing_identity_is_an_error(tmp_path) -> None:
    file = tmp_path / "identitet.toml"
    file.write_text('navn = "X"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="udgiver"):
        make_msix.identity(file)


def test_prepare_folder_writes_manifest_and_assets(tmp_path) -> None:
    (tmp_path / "Ordhjaelp.exe").write_text("")
    assert make_msix.main([str(tmp_path), "--version", "0.4.0.1"]) == 0
    assert (tmp_path / "AppxManifest.xml").exists()
    assert (tmp_path / "Assets" / "StoreLogo.png").exists()


# -- pakket eller ej ------------------------------------------------------------------
def test_is_packaged_reads_windows_answer() -> None:
    assert store.is_packaged(lambda: store.ERROR_INSUFFICIENT_BUFFER)
    assert not store.is_packaged(lambda: store.APPMODEL_ERROR_NO_PACKAGE)


def test_not_a_store_app_outside_windows() -> None:
    from ordhjaelp.platform import is_store_app

    if os.name != "nt":
        assert is_store_app() is False


# -- start ved login (StartupTask) ---------------------------------------------------
class FakeTasks:
    def __init__(self, state=StartupState.DISABLED, enable_to=StartupState.ENABLED):
        self._state = state
        self._enable_to = enable_to
        self.disabled = 0

    def state(self):
        return self._state

    def request_enable(self):
        if self._state not in (StartupState.DISABLED_BY_USER, StartupState.DISABLED_BY_POLICY):
            self._state = self._enable_to
        return self._state

    def disable(self):
        self.disabled += 1
        self._state = StartupState.DISABLED


def test_store_autostart_turns_on_and_off() -> None:
    tasks = FakeTasks()
    autostart = StoreAutostart(tasks)
    assert not autostart.is_enabled()
    autostart.set_enabled(True)
    assert autostart.is_enabled()
    autostart.set_enabled(False)
    assert not autostart.is_enabled() and tasks.disabled == 1


def test_store_autostart_respects_the_users_choice_in_windows() -> None:
    # Har eleven slået Ordhjælp fra under Indstillinger → Apps → Start, kan kun eleven
    # selv slå det til igen. Forklar hvor (indstillingsvinduet viser OSError i loggen).
    autostart = StoreAutostart(FakeTasks(StartupState.DISABLED_BY_USER))
    with pytest.raises(OSError, match="Apps → Start"):
        autostart.set_enabled(True)


def test_store_autostart_respects_policy() -> None:
    autostart = StoreAutostart(FakeTasks(StartupState.DISABLED_BY_POLICY))
    with pytest.raises(OSError, match="administrator"):
        autostart.set_enabled(True)
    forced = FakeTasks(StartupState.ENABLED_BY_POLICY)
    StoreAutostart(forced).set_enabled(False)  # kan ikke slås fra: ingen fejl, intet kald
    assert forced.disabled == 0 and StoreAutostart(forced).is_enabled()


def test_startup_task_errors_become_oserror() -> None:
    async def fails():
        raise RuntimeError("WinRT mangler")

    with pytest.raises(OSError, match="WinRT mangler"):
        store._run(fails)


# -- installer/afinstaller og ordforslag i Store-udgaven ------------------------------
@pytest.mark.parametrize("cmd", ["installer", "afinstaller"])
def test_store_app_does_not_install_itself(cmd, monkeypatch, tmp_path, capsys) -> None:
    from ordhjaelp import config as config_mod
    from ordhjaelp import platform

    monkeypatch.setattr(config_mod, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(platform, "is_store_app", lambda: True)
    assert cli.main([cmd]) == 1
    assert "Microsoft Store" in capsys.readouterr().err


def test_store_app_starts_without_word_suggestions() -> None:
    # Ordforslag lytter til alle tastetryk: fra Store skal eleven selv slå det til
    assert default_config(store_app=True).prediction_enabled is False
    assert default_config(store_app=False).prediction_enabled is True
    assert default_config(store_app=False) == Config()


def test_log_does_not_keep_the_students_text(caplog) -> None:
    # På Windows skrives loggen i en fil. Uden -v må elevens tekst ikke stå i den.
    import logging

    import numpy as np

    from ordhjaelp.services.dictation import MIN_SECONDS, SAMPLE_RATE, DictationService

    class Rec:
        def start(self):
            pass

        def stop(self):
            return np.zeros(int(SAMPLE_RATE * (MIN_SECONDS + 1)), dtype=np.float32)

    class Stt:
        def transcribe(self, audio):
            return "min hemmelige dagbog"

    class Inj:
        def insert(self, text):
            pass

    service = DictationService(recorder=Rec(), transcriber=Stt(), injector=Inj())
    with caplog.at_level(logging.INFO):
        service._transcribe_and_insert(Rec().stop())
    assert "hemmelige" not in caplog.text
    assert "Dikteret 20 tegn" in caplog.text
