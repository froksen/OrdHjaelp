"""Markeret tekst på Linux (Wayland og X11).

På Linux findes "primary selection": den tekst, der er markeret med musen,
uden at brugeren har trykket Ctrl+C.
"""

from __future__ import annotations

import os
import shutil
import subprocess

_TIMEOUT = 2.0


def _session_type() -> str:
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return "wayland"
    return "x11"


def _commands(primary: bool) -> list[list[str]]:
    if _session_type() == "wayland":
        cmd = ["wl-paste", "--no-newline", "--type", "text"]
        return [cmd + ["--primary"] if primary else cmd]
    sel = "primary" if primary else "clipboard"
    return [
        ["xclip", "-o", "-selection", sel],
        ["xsel", "--primary" if primary else "--clipboard", "--output"],
    ]


def _run(cmds: list[list[str]]) -> str | None:
    for cmd in cmds:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=_TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            continue
        if result.returncode != 0:
            continue
        text = result.stdout.decode("utf-8", errors="replace").strip()
        return text or None
    return None


class LinuxSelection:
    def selected_text(self) -> str | None:
        return _run(_commands(primary=True))

    def clipboard_text(self) -> str | None:
        return _run(_commands(primary=False))
