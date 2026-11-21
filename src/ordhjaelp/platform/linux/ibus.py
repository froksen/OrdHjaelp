"""Start Ordhjælps IBus-indtastningsmetode (ordforslag i alle programmer).

Kræver at IBus er valgt som indtastningsmetode i KDE:
Systemindstillinger → Tastatur → Virtuelt tastatur → "IBus Wayland".
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from importlib.resources import as_file, files

from ordhjaelp.platform.linux.selection import _die_with_parent

log = logging.getLogger(__name__)

SYSTEM_PYTHON = "/usr/bin/python3"  # har IBus-bindingerne (python3-gobject)


def ibus_running() -> bool:
    if shutil.which("ibus") is None:
        return False
    try:
        result = subprocess.run(["ibus", "address"], capture_output=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    address = result.stdout.decode().strip()
    return result.returncode == 0 and bool(address) and "(null)" not in address


class IBusInputMethod:
    def __init__(self, activate: bool = True) -> None:
        self._activate = activate
        self._proc: subprocess.Popen | None = None
        self._script_ctx = None
        self._stopping = threading.Event()

    def start(self) -> bool:
        self._script_ctx = as_file(files("ordhjaelp.platform.linux").joinpath("ibus_engine.py"))
        self._script = self._script_ctx.__enter__()
        running = ibus_running()
        if running:
            self._launch()
            log.info("Ordforslag (IBus) er startet")
        else:
            log.warning(
                "Ordforslag kræver IBus: vælg 'IBus Wayland' under Systemindstillinger → "
                "Tastatur → Virtuelt tastatur. Ordforslag starter af sig selv bagefter."
            )
        # Holder øje: starter motoren, når IBus kommer (igen) – fx efter genstart af IBus
        threading.Thread(target=self._watch, daemon=True, name="ibus-watch").start()
        return running

    def _launch(self) -> None:
        cmd = [SYSTEM_PYTHON, str(self._script)]
        if self._activate:
            cmd.append("--aktiver")
        self._proc = subprocess.Popen(cmd, preexec_fn=_die_with_parent)

    def _watch(self) -> None:
        """Start motoren igen, hvis IBus genstartes (så forsvinder registreringen)."""
        while not self._stopping.wait(5):
            stopped = self._proc is None or self._proc.poll() is not None
            if stopped and ibus_running():
                log.info("IBus er klar – starter ordforslag")
                self._launch()

    def stop(self) -> None:
        self._stopping.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._script_ctx is not None:
            self._script_ctx.__exit__(None, None, None)
            self._script_ctx = None
