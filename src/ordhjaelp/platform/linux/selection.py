"""Markeret tekst på Linux (Wayland og X11).

På Linux findes "primary selection": den tekst, der er markeret med musen,
uden at brugeren har trykket Ctrl+C.

Problem: Programmer (Chrome, LibreOffice …) og KDE's Klipper bliver ved med at
udbyde den sidst markerede tekst, selv efter markeringen er fjernet på skærmen.
Løsning: Vi holder øje med, hvornår markeringen *ændrer sig*. Tekst, der allerede
er læst op, og som ikke er blevet markeret igen siden, regnes for gammel.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import shutil
import signal
import subprocess
import threading

log = logging.getLogger(__name__)

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


class FreshnessTracker:
    """Afgør om en markering er ny eller allerede læst op.

    serial er et tal, der stiger hver gang markeringen ændrer sig (eller None,
    hvis vi ikke kan overvåge ændringer – så sammenlignes kun teksten).
    """

    def __init__(self) -> None:
        self._last: tuple[str, int | None] | None = None

    def fresh(self, text: str | None, serial: int | None) -> str | None:
        if not text:
            return None
        if self._last is not None:
            last_text, last_serial = self._last
            if text == last_text and serial == last_serial:
                return None  # samme markering som sidst – allerede læst op
        self._last = (text, serial)
        return text


def _die_with_parent() -> None:
    """Sørg for at overvågningsprocessen lukker, når Ordhjælp lukker (Linux)."""
    with contextlib.suppress(OSError):
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG


class _SelectionWatcher:
    """Tæller ændringer af primary selection via `wl-paste --watch` (kun Wayland)."""

    def __init__(self) -> None:
        self.serial = 0
        self._proc = subprocess.Popen(
            ["wl-paste", "--primary", "--watch", "echo"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            preexec_fn=_die_with_parent,
        )
        threading.Thread(target=self._read, daemon=True, name="selection-watch").start()

    def _read(self) -> None:
        assert self._proc.stdout is not None
        for _ in self._proc.stdout:
            self.serial += 1

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None


class LinuxSelection:
    def __init__(self) -> None:
        self._primary = FreshnessTracker()
        self._clipboard = FreshnessTracker()
        self._watcher: _SelectionWatcher | None = None
        if _session_type() == "wayland" and shutil.which("wl-paste"):
            try:
                self._watcher = _SelectionWatcher()
            except OSError as exc:
                log.warning("Kan ikke overvåge markeringer: %s", exc)

    def _serial(self) -> int | None:
        if self._watcher and self._watcher.alive:
            return self._watcher.serial
        return None

    def selected_text(self) -> str | None:
        return self._primary.fresh(_run(_commands(primary=True)), self._serial())

    def clipboard_text(self) -> str | None:
        # Udklipsholderen overvåges ikke – samme tekst to gange regnes for gammel.
        return self._clipboard.fresh(_run(_commands(primary=False)), None)
