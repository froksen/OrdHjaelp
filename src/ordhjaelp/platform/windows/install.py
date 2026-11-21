"""Autostart på Windows: en værdi under HKCU\\...\\Run (kun for den aktuelle bruger)."""

from __future__ import annotations

import contextlib
import shutil
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Ordhjaelp"


def start_command(executable: str = sys.executable, entry_point: str | None = None) -> str:
    """Kommandoen der starter Ordhjælp ved login, uden et sort konsolvindue."""
    if entry_point:
        return f'"{entry_point}" start'
    exe = Path(executable)
    windowless = exe.with_name("pythonw.exe")
    if exe.name.lower() == "python.exe" and windowless.exists():
        exe = windowless
    return f'"{exe}" -m ordhjaelp start'


def _command() -> str:
    return start_command(entry_point=shutil.which("ordhjaelp"))


class WindowsAutostart:
    def is_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, VALUE_NAME)
            return True
        except FileNotFoundError:
            return False

    def set_enabled(self, enabled: bool) -> None:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
            else:
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(key, VALUE_NAME)
