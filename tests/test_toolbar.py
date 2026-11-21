import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint, QRect, QSize, Qt  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp.config import VIEW_TOOLBAR, VIEW_TRAY, Config  # noqa: E402
from ordhjaelp.services.dictation import DictationState  # noqa: E402
from ordhjaelp.ui.settings import SettingsHooks  # noqa: E402
from ordhjaelp.ui.toolbar import load_state, place_on_screen  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def own_config_dir(tmp_path, monkeypatch):
    """Knaplinjen husker sin placering: aldrig i brugerens rigtige mappe."""
    from ordhjaelp import config as config_mod

    monkeypatch.setattr(config_mod, "config_dir", lambda: tmp_path)
    return tmp_path


class FakeService:
    def __init__(self):
        self.listeners = []
        self.toggled = 0

    def add_listener(self, fn):
        self.listeners.append(fn)

    def toggle(self):
        self.toggled += 1

    read_selection = stop = toggle


class FakeScreen:
    pass


def make_tray(view=VIEW_TOOLBAR, icons=None):
    from ordhjaelp.ui.tray import TrayApp

    cfg = Config()
    cfg.view = view
    if icons:
        cfg.show_icons.update(icons)
    hooks = SettingsHooks(
        config=cfg,
        set_speed=lambda v: None,
        say=lambda t: None,
        set_clipboard_fallback=lambda v: None,
        set_icon_visible=lambda n, v: None,
        restart=lambda: None,
    )
    service, dictation = FakeService(), FakeService()
    tray = TrayApp(service, dictation, FakeScreen(), {}, hooks, Config().hotkeys)
    tray.set_view(view)
    return tray, service, dictation, hooks


def test_toolbar_is_default_view() -> None:
    assert Config().view == VIEW_TOOLBAR


def test_view_roundtrips_and_unknown_falls_back() -> None:
    cfg = Config()
    cfg.view = VIEW_TRAY
    assert Config.from_toml(cfg.to_toml()).view == VIEW_TRAY
    assert Config.from_toml('[visning]\nknapper = "noget"\n').view == VIEW_TOOLBAR


def test_toolbar_never_takes_focus(app) -> None:
    tray, *_ = make_tray()
    bar = tray.toolbar
    assert bar.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert bar.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    for button in bar.buttons.values():
        assert button.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_toolbar_view_hides_extra_tray_icons(app) -> None:
    tray, *_ = make_tray(VIEW_TOOLBAR)
    assert tray.toolbar.isVisible()
    assert not tray.mic.isVisible() and not tray.screen_icon.isVisible()
    assert not tray.pdf_icon.isVisible()
    assert not tray.tray.isVisible()  # intet ved uret, når knaplinjen bruges
    assert set(tray.toolbar.buttons) == {"laes", "dikter", "skaerm", "pdf"}
    tray.toolbar.hide()


def test_tray_view_hides_toolbar_and_can_switch_live(app) -> None:
    tray, *_ = make_tray(VIEW_TRAY)
    assert not tray.toolbar.isVisible()
    assert tray.mic.isVisible() and tray.screen_icon.isVisible()
    assert tray.tray.isVisible()  # det blå ikon med menuen
    tray.set_view(VIEW_TOOLBAR)
    assert tray.toolbar.isVisible() and not tray.mic.isVisible()
    assert not tray.tray.isVisible()
    tray.toolbar.hide()


def test_buttons_call_the_services(app) -> None:
    tray, service, dictation, _ = make_tray()
    tray.toolbar.buttons["laes"].click()
    tray.toolbar.buttons["dikter"].click()
    assert service.toggled == 1 and dictation.toggled == 1
    tray.toolbar.hide()


def test_buttons_follow_state(app) -> None:
    tray, *_ = make_tray()
    tray._set_speaking(True)
    assert tray.toolbar.buttons["laes"].toolTip().startswith("Stop")
    assert "Ctrl+Alt+S" in tray.toolbar.buttons["laes"].toolTip()
    tray._set_speaking(False)
    tray._set_dictation_state(DictationState.RECORDING)
    assert tray.toolbar.buttons["dikter"].toolTip().startswith("Jeg lytter")
    tray.toolbar.hide()


def test_hidden_button_stays_hidden_after_unfold(app) -> None:
    tray, *_ = make_tray(icons={"skaerm": False})
    bar = tray.toolbar
    assert bar.buttons["skaerm"].isHidden()
    wide = bar.width()
    bar.set_folded(True)
    assert all(b.isHidden() for b in bar.buttons.values())
    assert bar.width() < wide / 2  # kun en lille fane er tilbage
    bar.set_folded(False)
    assert not bar.buttons["laes"].isHidden() and bar.buttons["skaerm"].isHidden()
    bar.hide()


def test_settings_dialog_switches_view(app, tmp_path) -> None:
    from ordhjaelp.ui.settings import SettingsDialog

    tray, _, _, hooks = make_tray(VIEW_TOOLBAR)
    dialog = SettingsDialog(hooks)
    assert dialog.view_toolbar.isChecked()
    dialog.view_tray.setChecked(True)
    dialog.accept()
    assert Config.from_toml((tmp_path / "config.toml").read_text()).view == VIEW_TRAY
    assert not tray.toolbar.isVisible() and tray.mic.isVisible()


# -- placeringen huskes ------------------------------------------------------
SCREEN = QRect(0, 0, 1366, 728)
SIZE = QSize(240, 52)


def test_saved_place_is_used_when_visible() -> None:
    assert place_on_screen(QPoint(100, 200), SIZE, [SCREEN]) == QPoint(100, 200)


def test_place_outside_screens_falls_back_to_near_clock() -> None:
    # Fx en ekstra skærm, der ikke er tilsluttet mere
    default = QPoint(1366 - 1 - 240 - 24, 728 - 1 - 52 - 24)
    assert place_on_screen(QPoint(2000, 200), SIZE, [SCREEN]) == default
    assert place_on_screen(QPoint(1300, 200), SIZE, [SCREEN]) == default  # halvt udenfor
    assert place_on_screen(None, SIZE, [SCREEN]) == default


def test_place_on_second_screen() -> None:
    second = QRect(1366, 0, 1920, 1040)
    assert place_on_screen(QPoint(2000, 300), SIZE, [SCREEN, second]) == QPoint(2000, 300)


def test_broken_state_file_is_ignored(tmp_path) -> None:
    path = tmp_path / "knaplinje.json"
    assert load_state(path) == {}
    path.write_text("{ikke json")
    assert load_state(path) == {}
    path.write_text("[1, 2]")
    assert load_state(path) == {}


def test_toolbar_remembers_place_and_fold(app, own_config_dir) -> None:
    tray, *_ = make_tray()
    bar = tray.toolbar
    bar.move(150, 120)
    bar.set_folded(True)
    bar._save()  # ellers efter et halvt sekund
    bar.hide()
    assert load_state(own_config_dir / "knaplinje.json") == {"foldet": True, "x": 150, "y": 120}

    again, *_ = make_tray()
    assert again.toolbar.pos() == QPoint(150, 120)
    assert again.toolbar.folded
    again.toolbar.hide()


def _bar_with_placer(answers):
    from ordhjaelp.ui.toolbar import Toolbar

    calls = []

    def placer(title, margin):
        calls.append((title, margin))
        return answers.pop(0)

    return Toolbar(QIcon(), wayland_placer=placer), calls


def test_wayland_asks_desktop_to_place_bar_in_corner(app, monkeypatch) -> None:
    """Wayland ignorerer move(): skrivebordet bedes flytte linjen. Prøver igen én gang."""
    from ordhjaelp.ui import toolbar as toolbar_mod

    monkeypatch.setattr(toolbar_mod, "_is_wayland", lambda: True)
    monkeypatch.setattr(toolbar_mod, "WAYLAND_PLACE_DELAYS", (0, 0))
    bar, calls = _bar_with_placer([False, True])
    bar.show_at_saved_place()
    deadline = time.monotonic() + 3
    while len(calls) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls == [("Ordhjælp", toolbar_mod.MARGIN)] * 2


def test_without_wayland_qt_places_bar_itself(app, monkeypatch) -> None:
    from ordhjaelp.ui import toolbar as toolbar_mod

    monkeypatch.setattr(toolbar_mod, "_is_wayland", lambda: False)
    bar, calls = _bar_with_placer([True])
    bar.show_at_saved_place()
    time.sleep(0.05)
    assert calls == []


def test_pdf_button_is_shown_by_default_and_opens_pdf_ocr(app, monkeypatch) -> None:
    """Knappen til at gøre en scannet PDF søgbar (OCR) er der fra start."""
    assert Config().show_icons["pdf"] is True
    from ordhjaelp.ui import pdf_ocr

    tray, *_ = make_tray()
    opened = []
    monkeypatch.setattr(pdf_ocr, "choose_pdf", lambda: opened.append(True))  # eleven fortryder
    button = tray.toolbar.buttons["pdf"]
    assert not button.isHidden()
    button.click()
    assert opened == [True]
    tray.toolbar.hide()


def test_pdf_button_can_be_hidden_and_shown_in_tray_view(app) -> None:
    tray, *_ = make_tray(VIEW_TRAY)
    assert tray.pdf_icon.isVisible()
    tray.set_icon_visible("pdf", False)
    assert not tray.pdf_icon.isVisible()
    assert tray.toolbar.buttons["pdf"].isHidden()


def test_fold_and_unfold_resizes_the_window_itself(app) -> None:
    """Vinduet får en fast størrelse. På Wayland beholdt skrivebordet ellers den gamle
    bredde, og den foldede fane kunne ikke foldes ud med et klik."""
    tray, *_ = make_tray()
    bar = tray.toolbar
    wide = bar.size()
    bar._fold.click()
    assert bar.folded
    assert bar.minimumSize() == bar.maximumSize() == bar.size()
    assert bar.width() < wide.width()
    assert bar._fold.text() == "›" and not bar._fold.icon().isNull()
    bar._fold.click()
    assert not bar.folded and bar.size() == wide
    assert all(not b.isHidden() for b in bar.buttons.values())
    bar.hide()
