"""Windows-delen. De rene dele testes overalt, resten kun på Windows (fx i CI)."""

import sys

import pytest

from ordhjaelp.platform.windows import win32
from ordhjaelp.platform.windows.hotkeys import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    parse_hotkey,
)
from ordhjaelp.platform.windows.install import start_command
from ordhjaelp.platform.windows.screenshot import bgra_to_png
from ordhjaelp.platform.windows.selection import copy_selection, is_shell_window

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="kræver Windows")


# -- genveje ----------------------------------------------------------------
@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        ("CTRL+ALT+L", (MOD_CONTROL | MOD_ALT, ord("L"))),
        ("ctrl+alt+1", (MOD_CONTROL | MOD_ALT, ord("1"))),
        ("META+R", (MOD_WIN, ord("R"))),
        ("SHIFT+F5", (MOD_SHIFT, 0x74)),
        ("CTRL+SPACE", (MOD_CONTROL, 0x20)),
        ("F12", (0, 0x7B)),
    ],
)
def test_parse_hotkey(trigger: str, expected: tuple[int, int]) -> None:
    assert parse_hotkey(trigger) == expected


@pytest.mark.parametrize("trigger", ["", "CTRL+ALT+Æ", "HYPER+L", "CTRL+F99"])
def test_parse_hotkey_rejects_unknown(trigger: str) -> None:
    with pytest.raises(ValueError):
        parse_hotkey(trigger)


def test_default_hotkeys_are_valid_on_windows() -> None:
    from ordhjaelp.config import Config

    for trigger in Config().hotkeys.values():
        parse_hotkey(trigger)


# -- tastatur ---------------------------------------------------------------
def test_unicode_inputs_press_and_release_each_char() -> None:
    items = win32.unicode_inputs("æø")
    assert [i.u.ki.wScan for i in items] == [ord("æ"), ord("æ"), ord("ø"), ord("ø")]
    assert items[1].u.ki.dwFlags & win32.KEYEVENTF_KEYUP
    assert all(i.u.ki.dwFlags & win32.KEYEVENTF_UNICODE for i in items)


def test_unicode_inputs_emoji_uses_surrogate_pair_and_newline_is_enter() -> None:
    items = win32.unicode_inputs("😀\n")
    assert len(items) == 6  # 2 surrogates x (ned, op) + Enter (ned, op)
    assert items[-1].u.ki.wVk == win32.VK_RETURN


def test_ctrl_c_inputs() -> None:
    vks = [i.u.ki.wVk for i in win32.ctrl_inputs(win32.VK_C)]
    assert vks == [win32.VK_CONTROL, win32.VK_C, win32.VK_C, win32.VK_CONTROL]


# -- skærmbillede -------------------------------------------------------------
def test_bgra_to_png_keeps_colors(tmp_path) -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QImage

    # 2x1 pixels: rød, blå (BGRA)
    png = bgra_to_png(2, 1, bytes([0, 0, 255, 255, 255, 0, 0, 255]))
    image = QImage.fromData(png)
    assert (image.width(), image.height()) == (2, 1)
    assert QColor(image.pixel(0, 0)).getRgb()[:3] == (255, 0, 0)
    assert QColor(image.pixel(1, 0)).getRgb()[:3] == (0, 0, 255)


def test_bgra_to_png_rejects_wrong_size() -> None:
    with pytest.raises(ValueError):
        bgra_to_png(2, 2, b"\x00" * 4)


# -- markeret tekst via Ctrl+C ----------------------------------------------
class FakeClipboard:
    def __init__(self, before: str | None, selected: str | None) -> None:
        self.text = before
        self.seq = 1
        self.selected = selected
        self.copies = 0
        self.focus_restored = 0

    def sequence_number(self) -> int:
        return self.seq

    def get_text(self) -> str | None:
        return self.text

    def set_text(self, text: str) -> None:
        self.text = text
        self.seq += 1

    def clear(self) -> None:
        self.text = None
        self.seq += 1

    def send_copy(self) -> None:
        self.copies += 1
        if self.selected is not None:  # programmet kopierer kun, hvis der er markeret noget
            self.set_text(self.selected)

    def restore_focus(self) -> None:
        self.focus_restored += 1


def _copy(clip: FakeClipboard) -> str | None:
    return copy_selection(clip, timeout=0.05, sleep=lambda _s: None)


def test_copy_selection_returns_text_and_restores_clipboard() -> None:
    clip = FakeClipboard(before="elevens egen tekst", selected="  skolen  ")
    assert _copy(clip) == "skolen"
    assert clip.text == "elevens egen tekst"
    assert clip.focus_restored == 1


def test_copy_selection_nothing_selected_leaves_clipboard_alone() -> None:
    clip = FakeClipboard(before="elevens egen tekst", selected=None)
    assert _copy(clip) is None
    assert clip.text == "elevens egen tekst"
    assert clip.seq == 1


def test_copy_selection_empty_clipboard_is_emptied_again() -> None:
    clip = FakeClipboard(before=None, selected="hej")
    assert _copy(clip) == "hej"
    assert clip.text is None


def test_shell_windows_are_ignored() -> None:
    assert is_shell_window("Shell_TrayWnd")
    assert not is_shell_window("Chrome_WidgetWin_1")


def test_selection_on_change_not_supported_yet() -> None:
    from ordhjaelp.platform.windows.selection import WindowsSelection

    sel = WindowsSelection(backend=FakeClipboard(None, None))
    assert sel.on_change(lambda: None) is False


# -- autostart ----------------------------------------------------------------
def test_start_command_prefers_entry_point() -> None:
    assert start_command(entry_point=r"C:\x\ordhjaelp.exe") == r'"C:\x\ordhjaelp.exe" start'


def test_start_command_uses_pythonw_when_present(tmp_path) -> None:
    (tmp_path / "python.exe").write_text("")
    (tmp_path / "pythonw.exe").write_text("")
    cmd = start_command(executable=str(tmp_path / "python.exe"))
    assert cmd == f'"{tmp_path / "pythonw.exe"}" -m ordhjaelp start'


# -- kun på Windows -----------------------------------------------------------
@windows_only
def test_input_struct_size_matches_windows() -> None:
    import ctypes

    assert ctypes.sizeof(win32.INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


@windows_only
def test_clipboard_roundtrip() -> None:
    from ordhjaelp.platform.windows import clipboard

    old = clipboard.get_text()
    try:
        before = clipboard.sequence_number()
        clipboard.set_text("Ærø og 😀")
        assert clipboard.get_text() == "Ærø og 😀"
        assert clipboard.sequence_number() != before
    finally:
        if old is None:
            clipboard.clear()
        else:
            clipboard.set_text(old)


@windows_only
def test_screenshot_is_png() -> None:
    from ordhjaelp.platform.windows.screenshot import WindowsScreenshot

    assert WindowsScreenshot().capture().startswith(b"\x89PNG")


@windows_only
def test_autostart_toggle_restores_state() -> None:
    from ordhjaelp.platform.windows.install import WindowsAutostart

    autostart = WindowsAutostart()
    original = autostart.is_enabled()
    try:
        autostart.set_enabled(True)
        assert autostart.is_enabled()
        autostart.set_enabled(False)
        assert not autostart.is_enabled()
    finally:
        autostart.set_enabled(original)


@windows_only
def test_hotkeys_start_and_stop() -> None:
    from ordhjaelp.platform.windows.hotkeys import WindowsHotkeys

    hotkeys = WindowsHotkeys()
    hotkeys.start({"laes": "CTRL+ALT+SHIFT+F11"}, lambda _a: None)
    hotkeys.stop()
