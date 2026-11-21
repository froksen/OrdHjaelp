"""Ikon ved uret: ét klik læser op, et klik mere stopper.

Qt virker på Linux, Windows og macOS, så denne fil ligger uden for platform/.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from collections.abc import Callable
from importlib.resources import as_file, files

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ordhjaelp import config
from ordhjaelp.config import APP_ID, VIEW_TOOLBAR, VIEW_TRAY
from ordhjaelp.services.dictation import DictationService, DictationState
from ordhjaelp.services.read_aloud import ReadAloudService
from ordhjaelp.services.screen_read import ScreenReadService

log = logging.getLogger(__name__)

TOOLTIP_IDLE = "Ordhjælp – markér tekst og klik her for at få den læst op"
TOOLTIP_SPEAKING = "Ordhjælp – klik for at stoppe"
MIC_TOOLTIPS = {
    DictationState.IDLE: "Diktér – klik og tal. Klik igen, når du er færdig",
    DictationState.RECORDING: "Jeg lytter … klik, når du er færdig",
    DictationState.TRANSCRIBING: "Jeg skriver det, du sagde …",
}
MIC_ICONS = {
    DictationState.IDLE: "ordhjaelp-mic",
    DictationState.RECORDING: "ordhjaelp-mic-rec",
    DictationState.TRANSCRIBING: "ordhjaelp-mic-wait",
}


PDF_TOOLTIP = "Gør en scannet PDF søgbar, så teksten kan markeres og læses op"


def _load_icon(name: str) -> QIcon:
    resource = files("ordhjaelp.ui").joinpath("icons", f"{name}.svg")
    with as_file(resource) as path:
        icon = QIcon(str(path))
        # Tving rasterisering mens filen findes (as_file kan være midlertidig)
        for size in (16, 22, 24, 32, 48, 64, 128):
            icon.addPixmap(icon.pixmap(size, size))
    return icon


class _Bridge(QObject):
    """Flytter beskeder fra baggrundstråde over i Qt's hovedtråd."""

    speaking_changed = Signal(bool)
    dictation_changed = Signal(object)
    screen_requested = Signal()
    screenshot_ready = Signal(object)  # bytes eller None
    screen_done = Signal()


class TrayApp:
    def __init__(
        self,
        service: ReadAloudService,
        dictation: DictationService | None = None,
        screen: ScreenReadService | None = None,
        ui_actions: dict[str, Callable[[], None]] | None = None,
        settings=None,  # noqa: ANN001 - SettingsHooks (importeres først ved brug)
        hotkeys: dict[str, str] | None = None,
    ) -> None:
        """:param hotkeys: de aktive genveje (vises i menuerne), None uden genveje."""
        from ordhjaelp.ui.shortcuts import shortcut_for, with_shortcut

        self._hotkeys = hotkeys
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setApplicationName("Ordhjælp")
        self.app.setDesktopFileName(APP_ID)
        self.app.setQuitOnLastWindowClosed(False)

        self._service = service
        self._icon_idle = _load_icon("ordhjaelp")
        self._icon_stop = _load_icon("ordhjaelp-stop")
        self.app.setWindowIcon(self._icon_idle)

        self.tray = QSystemTrayIcon(self._icon_idle)
        read_key = shortcut_for(hotkeys, "laes")
        self._tooltip_idle = TOOLTIP_IDLE + (f" (eller tryk {read_key})" if read_key else "")
        self.tray.setToolTip(self._tooltip_idle)
        self.tray.activated.connect(self._on_activated)

        menu = QMenu()
        self._act_read = QAction(with_shortcut("Læs markeret tekst op", hotkeys, "laes"), menu)
        self._act_read.triggered.connect(service.read_selection)
        self._act_stop = QAction(with_shortcut("Stop", hotkeys, "stop"), menu)
        self._act_stop.triggered.connect(service.stop)
        self._act_stop.setEnabled(False)
        act_quit = QAction("Luk Ordhjælp", menu)
        act_quit.triggered.connect(self.app.quit)
        menu.addAction(self._act_read)
        menu.addAction(self._act_stop)
        menu.addSeparator()
        # Slået fra som standard – slås til i indstillingerne
        self._act_pdf = QAction("Gør en PDF søgbar …", menu)
        self._act_pdf.triggered.connect(self.open_pdf_ocr)
        self._act_pdf.setVisible(bool(settings and settings.config.pdf_ocr_enabled))
        menu.addAction(self._act_pdf)
        self._pdf_jobs: list = []  # behold referencer, mens de kører
        act_keys = QAction("Genveje …", menu)
        act_keys.triggered.connect(self.open_shortcuts)
        menu.addAction(act_keys)
        self._tray_help_dialog = None
        if sys.platform == "win32":  # Windows 11 gemmer nye ikoner under ^
            act_tray_help = QAction("Vis ikonerne ved uret …", menu)
            act_tray_help.triggered.connect(self.open_tray_help)
            menu.addAction(act_tray_help)
        self._act_toolbar = QAction("Vis knaplinjen", menu)
        self._act_toolbar.triggered.connect(self.show_toolbar)
        menu.addAction(self._act_toolbar)
        self._settings = settings
        self._settings_dialog = None
        self._shortcuts_dialog = None
        self._view = settings.config.view if settings is not None else VIEW_TOOLBAR
        if settings is not None:
            settings.set_icon_visible = self.set_icon_visible
            settings.set_view = self.set_view
            settings.set_pdf_ocr = self._act_pdf.setVisible
            act_settings = QAction("Indstillinger …", menu)
            act_settings.triggered.connect(self.open_settings)
            menu.addAction(act_settings)
        menu.addAction(act_quit)
        self._menu = menu  # behold reference
        self.tray.setContextMenu(menu)

        self._bridge = _Bridge()
        self._bridge.speaking_changed.connect(self._set_speaking)
        service.add_listener(self._bridge.speaking_changed.emit)

        # Mikrofon-ikon (eget ikon ved uret, så det er let at forstå for børn)
        self.mic: QSystemTrayIcon | None = None
        if dictation is not None:
            self._dictation = dictation
            self._mic_icons = {st: _load_icon(name) for st, name in MIC_ICONS.items()}
            self.mic = QSystemTrayIcon(self._mic_icons[DictationState.IDLE])
            self.mic.setToolTip(MIC_TOOLTIPS[DictationState.IDLE])
            self.mic.activated.connect(self._on_mic_activated)
            mic_menu = QMenu()
            act_dictate = QAction(
                with_shortcut("Start/stop diktering", hotkeys, "dikter"), mic_menu
            )
            act_dictate.triggered.connect(dictation.toggle)
            mic_menu.addAction(act_dictate)
            self._mic_menu = mic_menu
            self.mic.setContextMenu(mic_menu)
            self._bridge.dictation_changed.connect(self._set_dictation_state)
            dictation.add_listener(self._bridge.dictation_changed.emit)

        # Læs-fra-skærmen-ikon
        self.screen_icon: QSystemTrayIcon | None = None
        self._screen = screen
        self._screen_busy = False
        self._picker = None
        if screen is not None:
            self._screen_icons = {
                False: _load_icon("ordhjaelp-screen"),
                True: _load_icon("ordhjaelp-screen-wait"),
            }
            self.screen_icon = QSystemTrayIcon(self._screen_icons[False])
            self.screen_icon.setToolTip("Læs fra skærmen – klik og træk en firkant om teksten")
            self.screen_icon.activated.connect(self._on_screen_activated)
            screen_menu = QMenu()
            act_screen = QAction(
                with_shortcut("Læs tekst fra skærmen", hotkeys, "skaerm"), screen_menu
            )
            act_screen.triggered.connect(self.start_screen_read)
            screen_menu.addAction(act_screen)
            self._screen_menu = screen_menu
            self.screen_icon.setContextMenu(screen_menu)
            self._bridge.screen_requested.connect(self.start_screen_read)
            self._bridge.screenshot_ready.connect(self._on_screenshot)
            self._bridge.screen_done.connect(lambda: self._set_screen_busy(False))
            if ui_actions is not None:
                # Genvejen kommer fra en baggrundstråd – send den via Qt-signal
                ui_actions["skaerm"] = self._bridge.screen_requested.emit

        # Gør en scannet PDF søgbar (OCR). Vises som standard som knap
        self._pdf_icon = _load_icon("ordhjaelp-pdf")
        self.pdf_icon = QSystemTrayIcon(self._pdf_icon)
        self.pdf_icon.setToolTip(PDF_TOOLTIP)
        self.pdf_icon.activated.connect(self._on_pdf_activated)

        self._build_toolbar(hotkeys)

    def _build_toolbar(self, hotkeys: dict[str, str] | None) -> None:
        """Knaplinjen med de samme funktioner som ikonerne ved uret."""
        from ordhjaelp.platform import move_window_to_corner
        from ordhjaelp.ui.toolbar import Toolbar, tooltip_with_key

        bar = Toolbar(
            self._icon_idle,
            self._menu,
            config.config_dir() / "knaplinje.json",
            wayland_placer=move_window_to_corner,
        )
        self._read_tip = tooltip_with_key("Læs markeret tekst op", hotkeys, "laes")
        self._stop_tip = tooltip_with_key("Stop oplæsningen", hotkeys, "stop")
        bar.add_button("laes", self._icon_idle, self._read_tip, self._service.toggle)
        if self.mic is not None:
            self._mic_tips = {
                st: tooltip_with_key(tip, hotkeys, "dikter") for st, tip in MIC_TOOLTIPS.items()
            }
            bar.add_button(
                "dikter",
                self._mic_icons[DictationState.IDLE],
                self._mic_tips[DictationState.IDLE],
                self._dictation.toggle,
            )
        if self.screen_icon is not None:
            self._screen_tip = tooltip_with_key(
                "Læs fra skærmen – træk en firkant om teksten", hotkeys, "skaerm"
            )
            bar.add_button(
                "skaerm", self._screen_icons[False], self._screen_tip, self.start_screen_read
            )
        bar.add_button("pdf", self._pdf_icon, PDF_TOOLTIP, self.open_pdf_ocr)
        self.toolbar = bar

    @staticmethod
    def available() -> bool:
        if QApplication.instance() is None:
            QApplication(sys.argv)
        return QSystemTrayIcon.isSystemTrayAvailable()

    def run(self, on_started: Callable[[], None] | None = None) -> int:
        self.tray.show()
        self.set_view(self._view)
        if sys.platform == "win32" and self._view == VIEW_TRAY:  # knaplinjen er ikke gemt
            QTimer.singleShot(3000, self._first_run_tray_tip)
        # Lad Ctrl+C/SIGTERM lukke pænt: Python ser kun signaler, når den får lov at køre.
        signal.signal(signal.SIGINT, lambda *_: self.app.quit())
        signal.signal(signal.SIGTERM, lambda *_: self.app.quit())
        timer = QTimer()
        timer.start(250)
        timer.timeout.connect(lambda: None)
        if on_started:
            QTimer.singleShot(0, on_started)
        return self.app.exec()

    # -- intern ---------------------------------------------------------
    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Kun enkeltklik: et dobbeltklik ville ellers starte og stoppe med det samme
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._service.toggle()

    # -- indstillinger --------------------------------------------------
    def open_settings(self) -> None:
        from ordhjaelp.ui.settings import SettingsDialog

        if self._settings_dialog is not None:  # allerede åben – vis den igen
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self._settings)
        dialog.setWindowIcon(self._icon_idle)
        dialog.finished.connect(lambda _: setattr(self, "_settings_dialog", None))
        self._settings_dialog = dialog
        dialog.show()

    # -- ikonerne ved uret (Windows 11 gemmer dem under ^) -------------
    def _first_run_tray_tip(self) -> None:
        """Første gang: fortæl, at ikonerne måske er gemt, og hvordan de vises."""
        from ordhjaelp.ui import tray_help

        try:
            if tray_help.take_help_request():  # valgt i velkomstvinduet
                self.open_tray_help()
                return
            if not tray_help.should_show_first_run_tip():
                return
            tray_help.remember_first_run_tip()
        except OSError:
            return
        self.tray.messageClicked.connect(self.open_tray_help)
        self.tray.showMessage(tray_help.TIP_TITLE, tray_help.TIP_TEXT, self._icon_idle, 15000)

    def open_tray_help(self) -> None:
        from ordhjaelp.platform import open_tray_icon_settings
        from ordhjaelp.ui.tray_help import TrayIconsHelpDialog

        if self._tray_help_dialog is None:
            self._tray_help_dialog = TrayIconsHelpDialog(open_tray_icon_settings)
            self._tray_help_dialog.setWindowIcon(self._icon_idle)
        self._tray_help_dialog.show()
        self._tray_help_dialog.raise_()
        self._tray_help_dialog.activateWindow()

    def open_shortcuts(self) -> None:
        from ordhjaelp.config import Config
        from ordhjaelp.ui.shortcuts import ShortcutsDialog

        cfg = self._settings.config if self._settings is not None else Config()
        if self._hotkeys is not None:
            cfg.hotkeys = dict(self._hotkeys)
        if self._shortcuts_dialog is None:
            self._shortcuts_dialog = ShortcutsDialog(cfg)
        self._shortcuts_dialog.show()
        self._shortcuts_dialog.raise_()
        self._shortcuts_dialog.activateWindow()

    def open_pdf_ocr(self) -> None:
        from ordhjaelp.ui.pdf_ocr import PdfOcrJob, choose_pdf

        src = choose_pdf()
        if src is None:
            return
        job = PdfOcrJob(src)
        job.dialog.setWindowIcon(self._icon_idle)
        job.on_done = lambda: self._pdf_jobs.remove(job)
        self._pdf_jobs.append(job)
        job.start()

    def set_icon_visible(self, name: str, visible: bool) -> None:
        if self._settings is not None:
            self._settings.config.show_icons[name] = visible
        icon = {"dikter": self.mic, "skaerm": self.screen_icon, "pdf": self.pdf_icon}.get(name)
        if icon is not None:
            icon.setVisible(visible and self._view == VIEW_TRAY)
        self.toolbar.set_button_visible(name, visible)

    # -- knaplinje eller ikoner ved uret ----------------------------------
    def set_view(self, view: str) -> None:
        """Skift mellem knaplinjen og ikonerne ved uret (uden genstart).

        Det blå ikon ved uret vises altid: det har menuen med indstillinger.
        """
        self._view = view
        icons = self._settings.config.show_icons if self._settings else {}
        for name, icon in (
            ("dikter", self.mic),
            ("skaerm", self.screen_icon),
            ("pdf", self.pdf_icon),
        ):
            if icon is not None:
                icon.setVisible(view == VIEW_TRAY and icons.get(name, True))
            self.toolbar.set_button_visible(name, icons.get(name, True))
        self._act_toolbar.setVisible(view == VIEW_TOOLBAR)
        if view == VIEW_TOOLBAR:
            if not self.toolbar.isVisible():
                self.toolbar.show_at_saved_place()
        else:
            self.toolbar.hide()

    def show_toolbar(self) -> None:
        """Vis knaplinjen foldet ud (menuen ved uret), fx hvis eleven har mistet den."""
        if not self.toolbar.isVisible():
            self.toolbar.show_at_saved_place()
        self.toolbar.set_folded(False)
        self.toolbar.raise_()

    # -- læs fra skærmen -----------------------------------------------
    def _on_screen_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.start_screen_read()

    def start_screen_read(self) -> None:
        if self._screen is None or self._screen_busy:
            return
        self._set_screen_busy(True)
        screen = self._screen
        threading.Thread(
            target=lambda: self._bridge.screenshot_ready.emit(screen.take_screenshot()),
            daemon=True,
            name="screenshot",
        ).start()

    def _on_screenshot(self, png: bytes | None) -> None:
        if png is None:
            self._set_screen_busy(False)
            return
        from ordhjaelp.ui.region_picker import RegionPicker

        self._picker = RegionPicker(png, self._on_region_picked, self._on_region_cancelled)
        self._picker.show()

    def _on_region_picked(self, png: bytes) -> None:
        self._picker = None
        screen = self._screen
        assert screen is not None

        def work() -> None:
            try:
                screen.read_image(png)
            finally:
                self._bridge.screen_done.emit()

        threading.Thread(target=work, daemon=True, name="ocr").start()

    def _on_region_cancelled(self) -> None:
        self._picker = None
        self._set_screen_busy(False)

    def _set_screen_busy(self, busy: bool) -> None:
        self._screen_busy = busy
        if self.screen_icon:
            self.screen_icon.setIcon(self._screen_icons[busy])
            tip = "Læser teksten på skærmen …" if busy else self._screen_tip
            self.toolbar.set_button("skaerm", self._screen_icons[busy], tip)

    def _on_pdf_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_pdf_ocr()

    def _on_mic_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._dictation.toggle()

    def _set_dictation_state(self, state: DictationState) -> None:
        assert self.mic is not None
        self.mic.setIcon(self._mic_icons[state])
        self.mic.setToolTip(MIC_TOOLTIPS[state])
        self.toolbar.set_button("dikter", self._mic_icons[state], self._mic_tips[state])

    def _set_speaking(self, speaking: bool) -> None:
        self.tray.setIcon(self._icon_stop if speaking else self._icon_idle)
        self.tray.setToolTip(TOOLTIP_SPEAKING if speaking else self._tooltip_idle)
        self._act_stop.setEnabled(speaking)
        self.toolbar.set_button(
            "laes",
            self._icon_stop if speaking else self._icon_idle,
            self._stop_tip if speaking else self._read_tip,
        )
