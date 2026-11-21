"""Læs ved markering på Windows: opdag, når eleven markerer tekst.

Windows melder ikke, når markeringen ændrer sig i et andet program. I stedet
holder vi øje med de bevægelser, der markerer tekst:

* træk med musen (markér et stykke tekst)
* dobbeltklik (et ord) og trippelklik (en linje eller et afsnit)
* Shift + piletaster, Home, End, Page Up/Down og Ctrl+A med tastaturet

Selve teksten hentes bagefter med UI Automation (se selection.py).
SelectionAutoReader venter et øjeblik, så et trippelklik ikke først læser ordet op.
"""

from __future__ import annotations

import ctypes
import logging
import math
import os
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

DRAG_DISTANCE = 5  # pixels: et klik, hvor musen flytter sig mere, er et træk
CLICK_DISTANCE = 4  # pixels: længere væk er det ikke et dobbeltklik
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_A = 0x41
SELECT_KEYS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28}  # PgUp PgDn End Home ← ↑ → ↓


class SelectionGestures:
    """Afgør ud fra musens tryk og slip, om eleven har markeret noget."""

    def __init__(self, double_click_ms: int = 500) -> None:
        self._double_click_ms = double_click_ms
        self._down: tuple[int, int, int] | None = None
        self._last_click: tuple[int, int, int] | None = None
        self._clicks = 0

    def mouse_down(self, x: int, y: int, ms: int) -> None:
        self._down = (x, y, ms)

    def mouse_up(self, x: int, y: int, ms: int) -> bool:
        """True, hvis tryk og slip har markeret tekst (træk, dobbelt- eller trippelklik)."""
        if self._down is None:
            return False
        dx, dy, down_ms = self._down
        self._down = None
        if math.dist((dx, dy), (x, y)) >= DRAG_DISTANCE:
            self._clicks = 0
            return True
        last = self._last_click
        if (
            last is not None
            and down_ms - last[2] <= self._double_click_ms
            and math.dist((last[0], last[1]), (x, y)) <= CLICK_DISTANCE
        ):
            self._clicks += 1
        else:
            self._clicks = 1
        self._last_click = (x, y, ms)
        return self._clicks >= 2

    @staticmethod
    def key(vk: int, shift: bool, ctrl: bool, alt: bool) -> bool:
        """True, hvis tasten markerer tekst (Shift+pil osv. eller Ctrl+A)."""
        if alt:
            return False
        if vk in SELECT_KEYS and shift:
            return True
        return vk == VK_A and ctrl and not shift


class GestureWatcher:
    """Overvåger mus og tastatur i en egen tråd og melder markeringer."""

    def __init__(self, on_selection: Callable[[], None]) -> None:
        self._on_selection = on_selection
        self._thread_id: int | None = None
        self._gestures: SelectionGestures | None = None

    def start(self) -> bool:
        ready = threading.Event()
        ok: list[bool] = []
        thread = threading.Thread(
            target=self._loop, args=(ready, ok), daemon=True, name="markering"
        )
        thread.start()
        ready.wait(5)
        return bool(ok and ok[0])

    def stop(self) -> None:
        if self._thread_id is not None:
            from ordhjaelp.platform.windows import win32

            win32.user32().PostThreadMessageW(self._thread_id, win32.WM_QUIT, 0, 0)

    def _loop(self, ready: threading.Event, ok: list[bool]) -> None:
        from ctypes import wintypes

        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        self._thread_id = win32.kernel32().GetCurrentThreadId()
        self._gestures = SelectionGestures(user32.GetDoubleClickTime())
        module = win32.kernel32().GetModuleHandleW(None)
        mouse_proc = win32.HOOKPROC(self._on_mouse)
        key_proc = win32.HOOKPROC(self._on_key)
        mouse_hook = user32.SetWindowsHookExW(win32.WH_MOUSE_LL, mouse_proc, module, 0)
        key_hook = user32.SetWindowsHookExW(win32.WH_KEYBOARD_LL, key_proc, module, 0)
        ok.append(bool(mouse_hook))
        if not mouse_hook:
            log.warning("Kan ikke holde øje med musen (fejl %s)", ctypes.get_last_error())
        ready.set()
        msg = wintypes.MSG()
        try:
            while mouse_hook and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            for hook in (mouse_hook, key_hook):
                if hook:
                    user32.UnhookWindowsHookEx(hook)
            del mouse_proc, key_proc

    def _notify(self) -> None:
        try:
            self._on_selection()
        except Exception:  # noqa: BLE001 - overvågningen må aldrig gå i stå
            log.exception("Fejl ved læs ved markering")

    def _on_mouse(self, code: int, wparam: int, lparam: int) -> int:
        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        if (
            code >= 0
            and self._gestures is not None
            and wparam
            in (
                win32.WM_LBUTTONDOWN,
                win32.WM_LBUTTONUP,
            )
        ):
            event = win32.MSLLHOOKSTRUCT.from_address(lparam)
            x, y = event.pt.x, event.pt.y
            if wparam == win32.WM_LBUTTONDOWN:
                self._gestures.mouse_down(x, y, event.time)
            elif self._gestures.mouse_up(x, y, event.time) and not _is_ours(
                user32.WindowFromPoint(event.pt)
            ):
                self._notify()
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _on_key(self, code: int, wparam: int, lparam: int) -> int:
        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        if code >= 0 and wparam in (win32.WM_KEYDOWN, win32.WM_SYSKEYDOWN):
            event = win32.KBDLLHOOKSTRUCT.from_address(lparam)

            def down(vk: int) -> bool:
                return bool(user32.GetAsyncKeyState(vk) & 0x8000)

            if SelectionGestures.key(event.vkCode, down(VK_SHIFT), down(VK_CONTROL), down(VK_MENU)):
                self._notify()
        return user32.CallNextHookEx(None, code, wparam, lparam)


def _is_ours(hwnd: int | None) -> bool:
    from ctypes import wintypes

    from ordhjaelp.platform.windows import win32

    if not hwnd:
        return False
    pid = wintypes.DWORD()
    win32.user32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()
