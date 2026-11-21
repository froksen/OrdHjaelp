"""Markeret tekst på Windows.

Først spørges programmet via UI Automation (se uia.py). Det rører ikke
udklipsholderen og virker i fx Word, Edge, Chrome og Notesblok.

Understøtter programmet ikke det, gør vi som andre LST-værktøjer: sender Ctrl+C
til programmet, læser udklipsholderen og lægger det, eleven havde kopieret,
tilbage bagefter. Aldrig i terminaler, hvor Ctrl+C stopper det, der kører.

Ændrer udklipsholderen sig ikke efter Ctrl+C, var der intet markeret. Derfor
kan en gammel markering ikke blive læst op igen ved en fejl.

Klik på ikonet ved uret flytter fokus til proceslinjen. Derfor husker vi det
sidste "rigtige" vindue og giver det fokus igen, før vi kopierer.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Protocol

from ordhjaelp.platform.freshness import FreshnessTracker

log = logging.getLogger(__name__)

COPY_TIMEOUT = 0.6  # så længe venter vi på, at programmet har kopieret
RESTORE_DELAY = 0.05
FOREGROUND_POLL = 0.25
# Terminaler: her afbryder Ctrl+C programmet i stedet for at kopiere
TERMINAL_CLASSES = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow"}
# Proceslinjen og dens ikonområder: dem vil vi ikke kopiere fra
SHELL_CLASSES = {
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
    "TopLevelWindowForOverflowXamlIsland",
    "Windows.UI.Core.CoreWindow",
}


class ClipboardBackend(Protocol):
    def sequence_number(self) -> int: ...
    def get_text(self) -> str | None: ...
    def set_text(self, text: str) -> None: ...
    def clear(self) -> None: ...
    def send_copy(self) -> None: ...
    def restore_focus(self) -> None: ...
    def foreground_class(self) -> str: ...


def copy_selection(
    backend: ClipboardBackend,
    timeout: float = COPY_TIMEOUT,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str | None:
    """Kopiér den markerede tekst og læg udklipsholderen tilbage, som den var."""
    try:
        previous = backend.get_text()
    except OSError as exc:
        log.warning("Kan ikke læse udklipsholderen: %s", exc)
        return None
    before = backend.sequence_number()
    backend.restore_focus()
    backend.send_copy()
    deadline = clock() + timeout
    while backend.sequence_number() == before and clock() < deadline:
        sleep(0.01)
    if backend.sequence_number() == before:
        return None  # intet blev kopieret, altså var intet markeret
    sleep(RESTORE_DELAY)  # nogle programmer skriver flere formater efter hinanden
    try:
        text = backend.get_text()
    finally:
        with contextlib.suppress(OSError):
            if previous is None:
                backend.clear()
            else:
                backend.set_text(previous)
    return text.strip() if text and text.strip() else None


class _Win32Backend:
    def __init__(self, focus: _ForegroundTracker) -> None:
        from ordhjaelp.platform.windows import clipboard

        self._clipboard = clipboard
        self._focus = focus

    def sequence_number(self) -> int:
        return self._clipboard.sequence_number()

    def get_text(self) -> str | None:
        return self._clipboard.get_text()

    def set_text(self, text: str) -> None:
        self._clipboard.set_text(text)

    def clear(self) -> None:
        self._clipboard.clear()

    def send_copy(self) -> None:
        from ordhjaelp.platform.windows import win32

        win32.wait_for_modifiers_released()
        win32.send_inputs(win32.ctrl_inputs(win32.VK_C))

    def restore_focus(self) -> None:
        self._focus.restore()

    def foreground_class(self) -> str:
        return self._focus.foreground_class()


def is_shell_window(class_name: str) -> bool:
    return class_name in SHELL_CLASSES


class _ForegroundTracker:
    """Husker det sidste vindue, eleven arbejdede i (ikke proceslinjen og ikke os selv)."""

    def __init__(self) -> None:
        from ordhjaelp.platform.windows import win32

        self._user32 = win32.user32()
        self._last: int | None = None
        threading.Thread(target=self._poll, daemon=True, name="foreground").start()

    def _class_name(self, hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        self._user32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    def _is_ours(self, hwnd: int) -> bool:
        from ctypes import wintypes

        pid = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()

    def _usable(self, hwnd: int | None) -> bool:
        return (
            bool(hwnd) and not self._is_ours(hwnd) and not is_shell_window(self._class_name(hwnd))
        )

    def _poll(self) -> None:
        while True:
            hwnd = self._user32.GetForegroundWindow()
            if self._usable(hwnd):
                self._last = hwnd
            time.sleep(FOREGROUND_POLL)

    def foreground_class(self) -> str:
        hwnd = self._user32.GetForegroundWindow()
        if not self._usable(hwnd) and self._last:
            hwnd = self._last  # proceslinjen eller os selv: det vindue, eleven kom fra
        return self._class_name(hwnd) if hwnd else ""

    def restore(self) -> None:
        current = self._user32.GetForegroundWindow()
        if self._usable(current) or not self._last:
            return
        if self._user32.SetForegroundWindow(self._last):
            time.sleep(0.1)  # giv vinduet tid til at få fokus, før Ctrl+C


def is_terminal(class_name: str) -> bool:
    return class_name in TERMINAL_CLASSES


def _uia_selection() -> str | None:
    from ordhjaelp.platform.windows import uia

    return uia.selected_text()


class WindowsSelection:
    def __init__(
        self,
        backend: ClipboardBackend | None = None,
        uia_selection: Callable[[], str | None] = _uia_selection,
    ) -> None:
        self._backend = backend or _Win32Backend(_ForegroundTracker())
        self._uia_selection = uia_selection
        self._clipboard = FreshnessTracker()
        self._watcher = None

    def selected_text(self) -> str | None:
        self._backend.restore_focus()  # klik på ikonet ved uret flytter fokus til proceslinjen
        text = self._uia_selection()
        if text and text.strip():
            return text.strip()
        if is_terminal(self._backend.foreground_class()):
            return None  # Ctrl+C ville stoppe det, der kører i terminalen
        return copy_selection(self._backend)

    def clipboard_text(self) -> str | None:
        try:
            return self._clipboard.fresh(self._backend.get_text(), None)
        except OSError:
            return None

    def on_change(self, callback: Callable[[], None]) -> bool:
        """Meld træk, dobbelt- og trippelklik og Shift+piletaster (se gestures.py)."""
        if self._watcher is not None:
            return True
        from ordhjaelp.platform.windows.gestures import GestureWatcher

        watcher = GestureWatcher(callback)
        if not watcher.start():
            return False
        self._watcher = watcher
        log.info("Læs ved markering holder øje med musen og tastaturet")
        return True
