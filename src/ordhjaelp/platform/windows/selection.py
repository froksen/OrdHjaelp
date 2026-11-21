"""Markeret tekst på Windows.

Windows har ingen "primary selection" som Linux. Vi gør som andre LST-værktøjer:
sender Ctrl+C til programmet, læser udklipsholderen og lægger det, eleven havde
kopieret, tilbage bagefter.

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

    def restore(self) -> None:
        current = self._user32.GetForegroundWindow()
        if self._usable(current) or not self._last:
            return
        if self._user32.SetForegroundWindow(self._last):
            time.sleep(0.1)  # giv vinduet tid til at få fokus, før Ctrl+C


class WindowsSelection:
    def __init__(self, backend: ClipboardBackend | None = None) -> None:
        self._backend = backend or _Win32Backend(_ForegroundTracker())
        self._clipboard = FreshnessTracker()

    def selected_text(self) -> str | None:
        return copy_selection(self._backend)

    def clipboard_text(self) -> str | None:
        try:
            return self._clipboard.fresh(self._backend.get_text(), None)
        except OSError:
            return None

    def on_change(self, callback: Callable[[], None]) -> bool:
        # Kræver UI Automation (kommer senere). Ctrl+C kan ikke bruges til at holde øje.
        log.warning("Læs ved markering er endnu ikke understøttet på Windows")
        return False
