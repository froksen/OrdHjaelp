"""Tynde ctypes-indpakninger af de Windows-funktioner, Ordhjælp bruger.

Ingen ekstra pakker (som pywin32): kun ctypes fra standardbiblioteket.
DLL'erne indlæses først, når de bruges, så modulet kan importeres (og strukturerne
testes) på Linux.
"""

from __future__ import annotations

import ctypes
import functools
import time
from ctypes import wintypes

# -- konstanter -------------------------------------------------------------
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_RETURN = 0x0D
VK_C = 0x43
MODIFIER_VKS = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


# -- strukturer til SendInput -------------------------------------------------
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    # MOUSEINPUT skal med, selv om vi kun sender taster: den bestemmer størrelsen
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def key_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    item = INPUT(type=INPUT_KEYBOARD)
    item.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def unicode_inputs(text: str) -> list[INPUT]:
    """Taste-hændelser, der skriver teksten uanset tastaturlayout (også æ, ø, å og emoji)."""
    items: list[INPUT] = []
    for char in text.replace("\r\n", "\n"):
        if char == "\n":
            items += [key_input(VK_RETURN), key_input(VK_RETURN, flags=KEYEVENTF_KEYUP)]
            continue
        data = char.encode("utf-16-le")
        for i in range(0, len(data), 2):  # tegn uden for BMP bliver til to "surrogates"
            unit = int.from_bytes(data[i : i + 2], "little")
            items += [
                key_input(scan=unit, flags=KEYEVENTF_UNICODE),
                key_input(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
            ]
    return items


def ctrl_inputs(vk: int) -> list[INPUT]:
    return [
        key_input(VK_CONTROL),
        key_input(vk),
        key_input(vk, flags=KEYEVENTF_KEYUP),
        key_input(VK_CONTROL, flags=KEYEVENTF_KEYUP),
    ]


# -- DLL'er (kun på Windows) ------------------------------------------------
@functools.cache
def user32():  # noqa: ANN201
    dll = ctypes.WinDLL("user32", use_last_error=True)
    dll.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    dll.SendInput.restype = wintypes.UINT
    dll.GetAsyncKeyState.argtypes = [ctypes.c_int]
    dll.GetAsyncKeyState.restype = ctypes.c_short
    dll.OpenClipboard.argtypes = [wintypes.HWND]
    dll.GetClipboardData.argtypes = [wintypes.UINT]
    dll.GetClipboardData.restype = wintypes.HANDLE
    dll.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    dll.SetClipboardData.restype = wintypes.HANDLE
    dll.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    dll.GetClipboardSequenceNumber.restype = wintypes.DWORD
    dll.GetForegroundWindow.restype = wintypes.HWND
    dll.SetForegroundWindow.argtypes = [wintypes.HWND]
    dll.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    dll.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    dll.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    dll.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    dll.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                                wintypes.UINT]  # fmt: skip
    dll.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM,
                                       wintypes.LPARAM]  # fmt: skip
    dll.GetDC.argtypes = [wintypes.HWND]
    dll.GetDC.restype = wintypes.HDC
    dll.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    return dll


@functools.cache
def kernel32():  # noqa: ANN201
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    dll.GlobalAlloc.restype = wintypes.HGLOBAL
    dll.GlobalLock.argtypes = [wintypes.HGLOBAL]
    dll.GlobalLock.restype = ctypes.c_void_p
    dll.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    dll.GlobalFree.argtypes = [wintypes.HGLOBAL]
    dll.GlobalFree.restype = wintypes.HGLOBAL
    dll.GetCurrentThreadId.restype = wintypes.DWORD
    return dll


@functools.cache
def gdi32():  # noqa: ANN201
    dll = ctypes.WinDLL("gdi32", use_last_error=True)
    dll.CreateCompatibleDC.argtypes = [wintypes.HDC]
    dll.CreateCompatibleDC.restype = wintypes.HDC
    dll.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    dll.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    dll.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    dll.SelectObject.restype = wintypes.HGDIOBJ
    dll.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                           wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]  # fmt: skip
    dll.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                              ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]  # fmt: skip
    dll.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    dll.DeleteDC.argtypes = [wintypes.HDC]
    return dll


# -- hjælpere ---------------------------------------------------------------
def send_inputs(items: list[INPUT]) -> None:
    if not items:
        return
    array = (INPUT * len(items))(*items)
    sent = user32().SendInput(len(items), array, ctypes.sizeof(INPUT))
    if sent != len(items):
        raise OSError(ctypes.get_last_error(), "SendInput blev afvist")


def modifiers_down() -> bool:
    return any(user32().GetAsyncKeyState(vk) & 0x8000 for vk in MODIFIER_VKS)


def wait_for_modifiers_released(timeout: float = 1.0) -> None:
    """Vent til Ctrl/Alt/Shift/Win er sluppet. Ellers bliver vores Ctrl+C til fx Ctrl+Alt+C."""
    deadline = time.monotonic() + timeout
    while modifiers_down() and time.monotonic() < deadline:
        time.sleep(0.02)
    if modifiers_down():  # stadig holdt nede: slip dem for eleven
        send_inputs([key_input(vk, flags=KEYEVENTF_KEYUP) for vk in MODIFIER_VKS])
