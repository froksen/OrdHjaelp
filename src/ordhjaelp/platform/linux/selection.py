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
import time
from collections.abc import Callable

from ordhjaelp.platform.freshness import FreshnessTracker

log = logging.getLogger(__name__)

__all__ = ["FreshnessTracker", "LinuxSelection"]

_TIMEOUT = 2.0
_STARTUP_GRACE = 1.0  # sekunder efter start, hvor meldinger om markeringen ignoreres
_X11_POLL_INTERVAL = 0.5  # X11 kan ikke melde ændringer, så vi kigger efter to gange i sekundet


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


def _die_with_parent() -> None:
    """Sørg for at overvågningsprocessen lukker, når Ordhjælp lukker (Linux)."""
    with contextlib.suppress(OSError):
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG


class _SelectionWatcher:
    """Tæller ændringer af primary selection via `wl-paste --watch` (kun Wayland)."""

    def __init__(self) -> None:
        self.serial = 0
        self._callbacks: list[Callable[[], None]] = []
        self._started = time.monotonic()
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
            # wl-paste melder måske også den markering, der fandtes ved start. Den er ikke ny.
            if time.monotonic() - self._started > _STARTUP_GRACE:
                _notify(self._callbacks)

    def add_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None


def _notify(callbacks: list[Callable[[], None]]) -> None:
    for callback in list(callbacks):
        try:
            callback()
        except Exception:
            log.exception("Fejl i lytter på markeringen")


class _X11SelectionPoller:
    """Kigger efter ændringer af primary selection på X11, hvor intet melder dem."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[[], None]] = []
        threading.Thread(target=self._poll, daemon=True, name="selection-poll").start()

    def add_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    def _poll(self) -> None:
        last = _run(_commands(primary=True))  # det, der er markeret nu, er ikke nyt
        while True:
            time.sleep(_X11_POLL_INTERVAL)
            text = _run(_commands(primary=True))
            if text and text != last:
                _notify(self._callbacks)
            last = text


class LinuxSelection:
    def __init__(self) -> None:
        self._primary = FreshnessTracker()
        self._clipboard = FreshnessTracker()
        self._watcher: _SelectionWatcher | None = None
        self._poller: _X11SelectionPoller | None = None
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

    def on_change(self, callback: Callable[[], None]) -> bool:
        if self._watcher and self._watcher.alive:
            self._watcher.add_callback(callback)
            return True
        if _session_type() == "x11" and any(shutil.which(c[0]) for c in _commands(True)):
            if self._poller is None:
                self._poller = _X11SelectionPoller()
            self._poller.add_callback(callback)
            return True
        log.warning("Kan ikke se, når markeringen ændrer sig (mangler wl-clipboard/xclip)")
        return False

    def clipboard_text(self) -> str | None:
        # Udklipsholderen overvåges ikke – samme tekst to gange regnes for gammel.
        return self._clipboard.fresh(_run(_commands(primary=False)), None)
