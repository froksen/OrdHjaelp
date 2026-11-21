"""Udklipsholderen på Windows (kun tekst)."""

from __future__ import annotations

import contextlib
import ctypes
import time
from collections.abc import Iterator

from ordhjaelp.platform.windows import win32


@contextlib.contextmanager
def _opened(attempts: int = 10) -> Iterator[None]:
    # Et andet program kan have udklipsholderen åben et øjeblik: prøv igen
    for _ in range(attempts):
        if win32.user32().OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        raise OSError(ctypes.get_last_error(), "Udklipsholderen er optaget")
    try:
        yield
    finally:
        win32.user32().CloseClipboard()


def sequence_number() -> int:
    """Tal, der stiger hver gang udklipsholderen ændres."""
    return int(win32.user32().GetClipboardSequenceNumber())


def get_text() -> str | None:
    user32, kernel32 = win32.user32(), win32.kernel32()
    with _opened():
        if not user32.IsClipboardFormatAvailable(win32.CF_UNICODETEXT):
            return None
        handle = user32.GetClipboardData(win32.CF_UNICODETEXT)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)


def set_text(text: str) -> None:
    user32, kernel32 = win32.user32(), win32.kernel32()
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    handle = kernel32.GlobalAlloc(win32.GMEM_MOVEABLE, size)
    if not handle:
        raise MemoryError("GlobalAlloc fejlede")
    pointer = kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, size)
    kernel32.GlobalUnlock(handle)
    with _opened():
        user32.EmptyClipboard()
        if not user32.SetClipboardData(win32.CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)  # ellers ejer Windows hukommelsen
            raise OSError(ctypes.get_last_error(), "SetClipboardData fejlede")


def clear() -> None:
    with _opened():
        win32.user32().EmptyClipboard()
