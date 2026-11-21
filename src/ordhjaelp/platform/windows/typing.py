"""Ordforslag og læs mens du skriver på Windows.

Windows har ingen IBus. I stedet lytter vi efter tastetryk i alle programmer med
en tastaturovervågning (SetWindowsHookEx med WH_KEYBOARD_LL) og viser forslagene
i et lille vindue ved markøren. Logikken ligger i typing_tracker.py.

Begrænsninger:
* Programmer, der kører som administrator, kan ikke overvåges af et almindeligt
  program. Der virker ordforslag ikke (Windows' sikkerhed, UIPI).
* Markørens plads findes via Windows' "caret". Nogle programmer (fx Chrome og
  Word) melder den ikke, og så vises forslagene ved musen.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import queue
import threading
from collections.abc import Callable

from ordhjaelp.platform.base import SetupCheck
from ordhjaelp.platform.windows.typing_tracker import TypingTracker, classify

log = logging.getLogger(__name__)

# Mærke på de taster, vi selv sender, så overvågningen ikke tæller dem med ("ORDH")
OUR_INPUT = 0x4F524448
TOUNICODE_KEEP_STATE = 0x4  # ToUnicodeEx må ikke ændre tastaturets tilstand (døde taster)

_active: WindowsInputMethod | None = None  # til opsætningstjekket


def caret_position() -> tuple[int, int, int] | None:
    """Markøren i det aktive program: (x, y, højde) i skærmpunkter, eller None."""
    from ctypes import wintypes

    from ordhjaelp.platform.windows import win32

    user32 = win32.user32()
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    thread = user32.GetWindowThreadProcessId(hwnd, None)
    info = win32.GUITHREADINFO(cbSize=ctypes.sizeof(win32.GUITHREADINFO))
    if not user32.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.hwndCaret:
        return None
    rect = info.rcCaret
    point = wintypes.POINT(rect.left, rect.top)
    if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(point)):
        return None
    return point.x, point.y, max(rect.bottom - rect.top, 1)


def mouse_position() -> tuple[int, int]:
    from ctypes import wintypes

    from ordhjaelp.platform.windows import win32

    point = wintypes.POINT()
    win32.user32().GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _replace(count: int, text: str) -> None:
    """Slet det skrevne ord, og skriv forslaget i stedet."""
    from ordhjaelp.platform.windows import win32

    win32.wait_for_modifiers_released(0.3)
    win32.send_inputs(
        win32.backspace_inputs(count, OUR_INPUT) + win32.unicode_inputs(text, OUR_INPUT)
    )


def _ipc_ask(word: str) -> list[str]:
    from ordhjaelp import ipc

    try:
        reply = ipc.send({"cmd": "forslag", "ord": word}, timeout=1.0)
    except ipc.CONNECT_ERRORS:
        return []
    return [str(w) for w in reply.get("forslag", [])]


def _ipc_tell(request: dict) -> None:
    """Send uden at vente på svar, så fx oplæsning ikke forsinker de næste forslag."""
    from ordhjaelp import ipc

    def send() -> None:
        with contextlib.suppress(*ipc.CONNECT_ERRORS):
            ipc.send(request, timeout=2.0)

    threading.Thread(target=send, daemon=True, name="ordforslag-besked").start()


class _Worker:
    """Én baggrundstråd, der gør tingene i rækkefølge (forslag, indsættelse, oplæsning)."""

    def __init__(self) -> None:
        self._queue: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ordforslag")
        self._thread.start()

    def submit(self, fn: Callable[[], None]) -> None:
        self._queue.put(fn)

    def stop(self) -> None:
        self._queue.put(None)

    def _run(self) -> None:
        while (fn := self._queue.get()) is not None:
            try:
                fn()
            except Exception:  # noqa: BLE001 - én fejl må ikke stoppe ordforslagene
                log.exception("Fejl i ordforslag")


class WindowsInputMethod:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._worker: _Worker | None = None
        self._popup = None
        self.tracker: TypingTracker | None = None
        self.listening = False
        self._held: set[int] = set()  # taster holdt tilbage: deres "slip" holdes også tilbage

    # -- InputMethod ------------------------------------------------------------
    def start(self) -> bool:
        global _active
        self._worker = _Worker()
        self._popup = _make_popup()
        popup = self._popup
        self.tracker = TypingTracker(
            ask=_ipc_ask,
            tell=_ipc_tell,
            show=popup.show_candidates if popup else lambda _c, _i: None,
            hide=popup.hide_candidates if popup else lambda: None,
            replace=_replace,
            run_async=self._worker.submit,
        )
        if popup is not None:
            popup.clicked.connect(self.tracker.click)
        ready = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, args=(ready,), daemon=True, name="tastatur"
        )
        self._thread.start()
        ready.wait(5)
        if self.listening:
            _active = self
        return self.listening

    def stop(self) -> None:
        global _active
        if _active is self:
            _active = None
        if self._thread_id is not None:
            from ordhjaelp.platform.windows import win32

            win32.user32().PostThreadMessageW(self._thread_id, win32.WM_QUIT, 0, 0)
        if self._worker is not None:
            self._worker.stop()
        if self._popup is not None:
            self._popup.hide_candidates()

    # -- overvågning --------------------------------------------------------------
    def _loop(self, ready: threading.Event) -> None:
        from ctypes import wintypes

        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        self._thread_id = win32.kernel32().GetCurrentThreadId()
        module = win32.kernel32().GetModuleHandleW(None)
        # Referencerne skal leve, så længe overvågningen kører
        key_proc = win32.HOOKPROC(self._on_key)
        mouse_proc = win32.HOOKPROC(self._on_mouse)
        focus_proc = win32.WINEVENTPROC(self._on_foreground)
        key_hook = user32.SetWindowsHookExW(win32.WH_KEYBOARD_LL, key_proc, module, 0)
        mouse_hook = user32.SetWindowsHookExW(win32.WH_MOUSE_LL, mouse_proc, module, 0)
        focus_hook = user32.SetWinEventHook(
            win32.EVENT_SYSTEM_FOREGROUND,
            win32.EVENT_SYSTEM_FOREGROUND,
            None,
            focus_proc,
            0,
            0,
            win32.WINEVENT_OUTOFCONTEXT,
        )
        self.listening = bool(key_hook)
        if not key_hook:
            log.warning("Kan ikke lytte efter tastetryk (fejl %s)", ctypes.get_last_error())
        else:
            log.info("Ordforslag lytter efter tastetryk")
        ready.set()
        msg = wintypes.MSG()
        try:
            while key_hook and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            self.listening = False
            for hook in (key_hook, mouse_hook):
                if hook:
                    user32.UnhookWindowsHookEx(hook)
            if focus_hook:
                user32.UnhookWinEvent(focus_hook)
            del key_proc, mouse_proc, focus_proc

    def _on_key(self, code: int, wparam: int, lparam: int) -> int:
        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        if code < 0 or self.tracker is None:
            return user32.CallNextHookEx(None, code, wparam, lparam)
        try:
            if self._handle_key(wparam, lparam):
                return 1  # hold tasten tilbage fra programmet
        except Exception:  # noqa: BLE001 - tastaturet må aldrig gå i stå
            log.exception("Fejl i tastaturovervågningen")
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _handle_key(self, wparam: int, lparam: int) -> bool:
        from ordhjaelp.platform.windows import win32

        assert self.tracker is not None
        event = win32.KBDLLHOOKSTRUCT.from_address(lparam)
        if wparam in (win32.WM_KEYUP, win32.WM_SYSKEYUP):
            if event.vkCode in self._held:
                self._held.discard(event.vkCode)
                return True
            return False
        if wparam not in (win32.WM_KEYDOWN, win32.WM_SYSKEYDOWN):
            return False
        if event.dwExtraInfo == OUR_INPUT:  # vores eget forslag, der skrives ind
            return False
        if event.flags & win32.LLKHF_INJECTED:  # fx diktering eller andre programmer
            self.tracker.reset()
            return False
        user32 = win32.user32()

        def down(vk: int) -> bool:
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)

        ctrl, alt = down(win32.VK_CONTROL), down(win32.VK_MENU)
        win = down(win32.VK_LWIN) or down(win32.VK_RWIN)
        char = _to_char(event.vkCode, event.scanCode, ctrl, alt)
        if char == "":  # død tast (fx ´ før é): ordet i programmet kan vi ikke følge
            self.tracker.reset()
            return False
        key = classify(event.vkCode, char, ctrl=ctrl, alt=alt, win=win)
        if key is None:
            return False
        if self.tracker.key(*key):
            self._held.add(event.vkCode)
            return True
        return False

    def _on_mouse(self, code: int, wparam: int, lparam: int) -> int:
        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        if (
            code >= 0
            and self.tracker is not None
            and wparam
            in (
                win32.WM_LBUTTONDOWN,
                win32.WM_RBUTTONDOWN,
                win32.WM_MBUTTONDOWN,
            )
        ):
            try:
                event = win32.MSLLHOOKSTRUCT.from_address(lparam)
                if not _is_ours(user32.WindowFromPoint(event.pt)):
                    self.tracker.reset()  # markøren flyttes nok med musen
            except Exception:  # noqa: BLE001
                log.exception("Fejl i musovervågningen")
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _on_foreground(self, *_args) -> None:  # noqa: ANN002
        if self.tracker is not None:
            self.tracker.reset()


def _is_ours(hwnd: int | None) -> bool:
    from ctypes import wintypes

    from ordhjaelp.platform.windows import win32

    if not hwnd:
        return False
    pid = wintypes.DWORD()
    win32.user32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


def _to_char(vk: int, scan: int, ctrl: bool, alt: bool) -> str | None:
    """Tegnet, tasten skriver med det aktive programs tastaturlayout.

    None = intet tegn, "" = død tast (accent, der venter på næste bogstav).
    """
    from ordhjaelp.platform.windows import win32

    user32 = win32.user32()
    state = (ctypes.c_ubyte * 256)()
    for shift_vk in (win32.VK_SHIFT, 0xA0, 0xA1):
        if user32.GetAsyncKeyState(shift_vk) & 0x8000:
            state[shift_vk] = 0x80
    if ctrl and alt:  # AltGr
        state[win32.VK_CONTROL] = state[win32.VK_LCONTROL] = 0x80
        state[win32.VK_MENU] = state[win32.VK_RMENU] = 0x80
    if user32.GetKeyState(win32.VK_CAPITAL) & 1:
        state[win32.VK_CAPITAL] = 0x01
    thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    layout = user32.GetKeyboardLayout(thread)
    buf = ctypes.create_unicode_buffer(8)
    count = user32.ToUnicodeEx(vk, scan, state, buf, 8, TOUNICODE_KEEP_STATE, layout)
    if count < 0:
        return ""
    if count == 0:
        return None
    return buf.value[:count]


def _make_popup():  # noqa: ANN202
    """Forslagsvinduet (Qt). None uden brugerflade – så virker kun læs mens du skriver."""
    try:
        from PySide6.QtWidgets import QApplication

        from ordhjaelp.ui.suggestions import SuggestionPopup
    except ImportError:
        return None
    if QApplication.instance() is None:
        QApplication([])
    return SuggestionPopup(caret_position, mouse_position)


# -- opsætningstjek og vejledning ---------------------------------------------
class WindowsTypingSetup:
    """På Windows skal intet sættes op. Tjekket viser, om Ordhjælp lytter efter tastetryk."""

    intro = (
        "Ordforslag og læs mens du skriver virker i alle almindelige programmer på "
        "Windows. Der skal ikke installeres eller slås noget til i Windows."
    )
    settings_button = None  # der er ingen systemindstillinger at åbne

    def checks(self) -> list[SetupCheck]:
        listening = _active is not None and _active.listening
        return [
            SetupCheck(
                "Ordhjælp lytter efter tastetryk",
                listening,
                "Gem indstillingerne. Ordhjælp starter ordforslag af sig selv.",
            )
        ]

    def guide(self) -> list[str]:
        return [
            "Sæt flueben ved ordforslag eller læs mens du skriver, og klik på <b>Gem</b>.",
            "Skriv i et program. Forslagene vises ved markøren, mens du skriver.",
            "Vælg et forslag med <b>F1–F5</b>, med musen eller med <b>↓ ↑</b> og <b>Tab</b>.",
            "Virker det ikke i et bestemt program? Kører programmet som administrator, "
            "kan Ordhjælp ikke hjælpe der.",
        ]

    def open_settings(self) -> bool:
        return False
