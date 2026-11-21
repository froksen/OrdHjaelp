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
VK_BACK = 0x08
VK_CAPITAL = 0x14
VK_LCONTROL = 0xA2
VK_RMENU = 0xA5  # AltGr
VK_C = 0x43
MODIFIER_VKS = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

# Tastatur- og musovervågning (low-level hooks)
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
LLKHF_INJECTED = 0x10
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008


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


# -- strukturer til tastatur- og musovervågning ---------------------------------
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


LRESULT = ctypes.c_ssize_t
# WINFUNCTYPE findes kun på Windows. CFUNCTYPE andre steder, så modulet kan importeres.
_FUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
HOOKPROC = _FUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WINEVENTPROC = _FUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                         wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)  # fmt: skip


def key_input(vk: int = 0, scan: int = 0, flags: int = 0, extra: int = 0) -> INPUT:
    item = INPUT(type=INPUT_KEYBOARD)
    item.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=extra)
    return item


def unicode_inputs(text: str, extra: int = 0) -> list[INPUT]:
    """Taste-hændelser, der skriver teksten uanset tastaturlayout (også æ, ø, å og emoji).

    :param extra: mærke på hændelserne, så vores egen tastaturovervågning kan kende dem
    """
    items: list[INPUT] = []
    for char in text.replace("\r\n", "\n"):
        if char == "\n":
            items += [
                key_input(VK_RETURN, extra=extra),
                key_input(VK_RETURN, flags=KEYEVENTF_KEYUP, extra=extra),
            ]
            continue
        data = char.encode("utf-16-le")
        for i in range(0, len(data), 2):  # tegn uden for BMP bliver til to "surrogates"
            unit = int.from_bytes(data[i : i + 2], "little")
            items += [
                key_input(scan=unit, flags=KEYEVENTF_UNICODE, extra=extra),
                key_input(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, extra=extra),
            ]
    return items


def backspace_inputs(count: int, extra: int = 0) -> list[INPUT]:
    items: list[INPUT] = []
    for _ in range(count):
        items += [
            key_input(VK_BACK, extra=extra),
            key_input(VK_BACK, flags=KEYEVENTF_KEYUP, extra=extra),
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
    # Tastatur- og musovervågning
    dll.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    dll.SetWindowsHookExW.restype = wintypes.HHOOK
    dll.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM,
                                   wintypes.LPARAM]  # fmt: skip
    dll.CallNextHookEx.restype = LRESULT
    dll.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    dll.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                                    WINEVENTPROC, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.DWORD]  # fmt: skip
    dll.SetWinEventHook.restype = wintypes.HANDLE
    dll.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    dll.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    dll.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    dll.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
                                wintypes.LPWSTR, ctypes.c_int, wintypes.UINT,
                                wintypes.HKL]  # fmt: skip
    dll.GetKeyboardLayout.argtypes = [wintypes.DWORD]
    dll.GetKeyboardLayout.restype = wintypes.HKL
    dll.GetKeyState.argtypes = [ctypes.c_int]
    dll.GetKeyState.restype = ctypes.c_short
    dll.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
    dll.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    dll.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    dll.WindowFromPoint.argtypes = [wintypes.POINT]
    dll.WindowFromPoint.restype = wintypes.HWND
    dll.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    dll.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    dll.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    dll.SetWindowLongPtrW.restype = ctypes.c_ssize_t
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
    dll.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    dll.GetModuleHandleW.restype = wintypes.HMODULE
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
