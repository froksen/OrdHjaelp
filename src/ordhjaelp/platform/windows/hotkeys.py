"""Globale genveje på Windows med RegisterHotKey.

Hver genvej registreres i en egen tråd med sin egen beskedløkke. Windows sender
WM_HOTKEY til den tråd, når genvejen trykkes, uanset hvilket program der har fokus.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

MODIFIERS = {
    "CTRL": MOD_CONTROL,
    "CONTROL": MOD_CONTROL,
    "ALT": MOD_ALT,
    "SHIFT": MOD_SHIFT,
    "META": MOD_WIN,
    "SUPER": MOD_WIN,
    "WIN": MOD_WIN,
}
NAMED_KEYS = {
    "SPACE": 0x20,
    "ENTER": 0x0D,
    "RETURN": 0x0D,
    "TAB": 0x09,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "PAUSE": 0x13,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
}


def parse_hotkey(trigger: str) -> tuple[int, int]:
    """'CTRL+ALT+L' -> (modifikatorer, virtuel tast) til RegisterHotKey."""
    parts = [p.strip().upper() for p in trigger.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"tom genvej: {trigger!r}")
    *mods, key = parts
    modifiers = 0
    for mod in mods:
        if mod not in MODIFIERS:
            raise ValueError(f"ukendt modifikator {mod!r} i {trigger!r}")
        modifiers |= MODIFIERS[mod]
    if len(key) == 1 and (key.isascii() and key.isalnum()):
        vk = ord(key)  # A-Z og 0-9 har samme kode som tegnet
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    else:
        raise ValueError(f"ukendt tast {key!r} i {trigger!r}")
    return modifiers, vk


class WindowsHotkeys:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

    def start(self, bindings: dict[str, str], on_activated: Callable[[str], None]) -> None:
        ready = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, args=(bindings, on_activated, ready), daemon=True, name="hotkeys"
        )
        self._thread.start()
        ready.wait(5)

    def stop(self) -> None:
        if self._thread_id is not None:
            from ordhjaelp.platform.windows import win32

            win32.user32().PostThreadMessageW(self._thread_id, win32.WM_QUIT, 0, 0)

    def _loop(
        self,
        bindings: dict[str, str],
        on_activated: Callable[[str], None],
        ready: threading.Event,
    ) -> None:
        from ctypes import wintypes

        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        self._thread_id = win32.kernel32().GetCurrentThreadId()
        actions: dict[int, str] = {}
        for hotkey_id, (action, trigger) in enumerate(bindings.items(), start=1):
            try:
                modifiers, vk = parse_hotkey(trigger)
            except ValueError as exc:
                log.warning("Genvejen til '%s' kan ikke bruges: %s", action, exc)
                continue
            if user32.RegisterHotKey(None, hotkey_id, modifiers | MOD_NOREPEAT, vk):
                actions[hotkey_id] = action
                log.info("Genvej %s: %s", action, trigger)
            else:
                log.warning(
                    "Genvejen %s til '%s' bruges allerede af et andet program. "
                    "Vælg en anden under [genveje] i indstillingsfilen.",
                    trigger,
                    action,
                )
        ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == win32.WM_HOTKEY and msg.wParam in actions:
                    # Egen tråd: fx Ctrl+C-kopiering må ikke holde beskedløkken op
                    threading.Thread(
                        target=on_activated, args=(actions[msg.wParam],), daemon=True
                    ).start()
        finally:
            for hotkey_id in actions:
                user32.UnregisterHotKey(None, hotkey_id)
