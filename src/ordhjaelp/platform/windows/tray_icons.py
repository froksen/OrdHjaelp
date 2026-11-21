"""Vis Ordhjælps ikoner ved uret, i stedet for gemt under ^ (Windows 11).

Windows 11 skjuler nye ikoner. Brugeren kan selv vælge "Vis på proceslinjen"
under Indstillinger → Personlige indstillinger → Proceslinje. Det valg gemmes pr.
program i HKCU\\Control Panel\\NotifyIconSettings\\<nummer> som IsPromoted.
Ordhjælp sætter det for sit eget program. Det kræver ikke administrator.

Windows opretter nøglen, første gang et ikon vises. Derfor kaldes promote()
lidt efter, at ikonerne er vist.

Bemærk: Windows gemmer valget pr. program. Kører Ordhjælp fra kildekoden, er
programmet pythonw.exe, og så gælder valget også andre Python-programmers ikoner.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import re
from ctypes import wintypes
from pathlib import Path

log = logging.getLogger(__name__)

SETTINGS_KEY = r"Control Panel\NotifyIconSettings"
# Windows skriver fx {6D809377-6AF0-444B-8957-A3773F02200E}\Programmer\x.exe for Program Files
_KNOWN_FOLDER = re.compile(r"^\{([0-9A-Fa-f-]{36})\}(.*)$")


def own_executable() -> str:
    """Den .exe, processen faktisk kører (i et venv: Pythons egen pythonw.exe)."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    size = wintypes.DWORD(32768)
    buf = ctypes.create_unicode_buffer(size.value)
    if not kernel32.QueryFullProcessImageNameW(
        kernel32.GetCurrentProcess(), 0, buf, ctypes.byref(size)
    ):
        raise OSError(ctypes.get_last_error(), "QueryFullProcessImageNameW")
    return buf.value


def _known_folder(guid: str) -> str | None:
    from ordhjaelp.platform.windows.uia import GUID

    shell32 = ctypes.WinDLL("shell32")
    ole32 = ctypes.WinDLL("ole32")
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    out = ctypes.c_wchar_p()
    folder = GUID.parse("{" + guid + "}")
    if shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(out)) != 0:
        return None
    try:
        return out.value
    finally:
        ole32.CoTaskMemFree(ctypes.cast(out, ctypes.c_void_p))


def expand(path: str, known_folder=_known_folder) -> str:  # noqa: ANN001
    """Windows' sti med {mappe-GUID} foran → almindelig sti."""
    match = _KNOWN_FOLDER.match(path)
    if not match:
        return path
    base = known_folder(match.group(1))
    return base + match.group(2) if base else path


def same_file(a: str, b: str) -> bool:
    return Path(a).resolve(strict=False).as_posix().lower() == (
        Path(b).resolve(strict=False).as_posix().lower()
    )


def set_promoted(promoted: bool, executable: str | None = None) -> int:
    """Vis (eller gem) Ordhjælps ikoner ved uret. Returnerer antal ændrede ikoner."""
    import winreg

    exe = executable or own_executable()
    changed = 0
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, SETTINGS_KEY)
    except FileNotFoundError:
        return 0  # Windows 10: findes ikke (der vælges ikoner på en anden måde)
    with root:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            with (
                contextlib.suppress(OSError),
                winreg.OpenKey(root, name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key,
            ):
                path, _ = winreg.QueryValueEx(key, "ExecutablePath")
                if not same_file(expand(str(path)), exe):
                    continue
                try:
                    current, _ = winreg.QueryValueEx(key, "IsPromoted")
                except FileNotFoundError:
                    current = None
                if current != int(promoted):
                    winreg.SetValueEx(key, "IsPromoted", 0, winreg.REG_DWORD, int(promoted))
                    changed += 1
    if changed:
        log.info("Ikonerne ved uret: %s", "vises altid" if promoted else "må skjules")
    return changed
