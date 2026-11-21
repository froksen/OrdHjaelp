"""Ikon ved uret: ét klik læser op, et klik mere stopper.

Qt virker på Linux, Windows og macOS, så denne fil ligger uden for platform/.
"""

from __future__ import annotations

import logging
import signal
import sys
from collections.abc import Callable
from importlib.resources import as_file, files

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ordhjaelp.config import APP_ID
from ordhjaelp.services.dictation import DictationService, DictationState
from ordhjaelp.services.read_aloud import ReadAloudService

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


class TrayApp:
    def __init__(
        self, service: ReadAloudService, dictation: DictationService | None = None
    ) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setApplicationName("Ordhjælp")
        self.app.setDesktopFileName(APP_ID)
        self.app.setQuitOnLastWindowClosed(False)

        self._service = service
        self._icon_idle = _load_icon("ordhjaelp")
        self._icon_stop = _load_icon("ordhjaelp-stop")
        self.app.setWindowIcon(self._icon_idle)

        self.tray = QSystemTrayIcon(self._icon_idle)
        self.tray.setToolTip(TOOLTIP_IDLE)
        self.tray.activated.connect(self._on_activated)

        menu = QMenu()
        self._act_read = QAction("Læs markeret tekst op", menu)
        self._act_read.triggered.connect(service.read_selection)
        self._act_stop = QAction("Stop", menu)
        self._act_stop.triggered.connect(service.stop)
        self._act_stop.setEnabled(False)
        act_quit = QAction("Luk Ordhjælp", menu)
        act_quit.triggered.connect(self.app.quit)
        menu.addAction(self._act_read)
        menu.addAction(self._act_stop)
        menu.addSeparator()
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
            act_dictate = QAction("Start/stop diktering", mic_menu)
            act_dictate.triggered.connect(dictation.toggle)
            mic_menu.addAction(act_dictate)
            self._mic_menu = mic_menu
            self.mic.setContextMenu(mic_menu)
            self._bridge.dictation_changed.connect(self._set_dictation_state)
            dictation.add_listener(self._bridge.dictation_changed.emit)

    @staticmethod
    def available() -> bool:
        if QApplication.instance() is None:
            QApplication(sys.argv)
        return QSystemTrayIcon.isSystemTrayAvailable()

    def run(self, on_started: Callable[[], None] | None = None) -> int:
        self.tray.show()
        if self.mic:
            self.mic.show()
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

    def _on_mic_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._dictation.toggle()

    def _set_dictation_state(self, state: DictationState) -> None:
        assert self.mic is not None
        self.mic.setIcon(self._mic_icons[state])
        self.mic.setToolTip(MIC_TOOLTIPS[state])

    def _set_speaking(self, speaking: bool) -> None:
        self.tray.setIcon(self._icon_stop if speaking else self._icon_idle)
        self.tray.setToolTip(TOOLTIP_SPEAKING if speaking else TOOLTIP_IDLE)
        self._act_stop.setEnabled(speaking)
