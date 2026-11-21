"""Start Ordhjælps IBus-indtastningsmetode (ordforslag i alle programmer).

Kræver at IBus er valgt som indtastningsmetode i KDE:
Systemindstillinger → Tastatur → Virtuelt tastatur → "IBus Wayland".
"""

from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
import threading
from importlib.resources import as_file, files

from ordhjaelp.platform.base import SetupCheck
from ordhjaelp.platform.linux.selection import _die_with_parent, _session_type

log = logging.getLogger(__name__)

SYSTEM_PYTHON = "/usr/bin/python3"  # har IBus-bindingerne (python3-gobject)
ENGINE_NAME = "ordhjaelp"  # samme navn som i ibus_engine.py
KDE_KEYBOARD_KCM = "kcm_virtualkeyboard"  # Systemindstillinger → Tastatur → Virtuelt tastatur


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


# -- opsætningstjek og vejledning ---------------------------------------------


def _is_kde_wayland() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "") and _session_type() == "wayland"


@functools.cache
def _ibus_installed() -> bool:
    """IBus og de Python-bindinger, som Ordhjælps motor kører med. Ændrer sig ikke undervejs."""
    if shutil.which("ibus") is None:
        return False
    probe = "import gi; gi.require_version('IBus', '1.0'); from gi.repository import IBus"
    try:
        result = subprocess.run([SYSTEM_PYTHON, "-c", probe], capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _kwin_input_method() -> str:
    """Det virtuelle tastatur, der er valgt i KDE (tom tekst, hvis intet er valgt)."""
    if shutil.which("kreadconfig6") is None:
        return ""
    try:
        result = subprocess.run(
            ["kreadconfig6", "--file", "kwinrc", "--group", "Wayland", "--key", "InputMethod"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def _current_engine() -> str:
    try:
        result = subprocess.run(
            ["ibus", "engine"], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


class IBusSetup:
    """Tjekker, om IBus er sat op, så ordforslag og læs mens du skriver virker."""

    def checks(self) -> list[SetupCheck]:
        installed = _ibus_installed()
        result = [
            SetupCheck(
                "IBus er installeret",
                installed,
                "Installér IBus: sudo dnf install ibus python3-gobject",
            )
        ]
        if _is_kde_wayland():
            chosen = "ibus" in _kwin_input_method().lower()
            result.append(
                SetupCheck(
                    "IBus er valgt som virtuelt tastatur",
                    chosen,
                    "Vælg »IBus Wayland« under Systemindstillinger → Tastatur → Virtuelt tastatur.",
                )
            )
        running = installed and ibus_running()
        result.append(
            SetupCheck("IBus kører", running, "IBus starter, når det er valgt som tastatur.")
        )
        connected = running and _current_engine() == ENGINE_NAME
        result.append(
            SetupCheck(
                "Ordhjælp er koblet på IBus",
                connected,
                "Gem indstillingerne. Ordhjælp kobler sig på af sig selv efter nogle sekunder.",
            )
        )
        return result

    def guide(self) -> list[str]:
        steps = []
        if not _ibus_installed():
            steps.append(
                "Installér IBus. Skriv i en terminal: <b>sudo dnf install ibus python3-gobject</b>"
            )
        if _is_kde_wayland():
            steps += [
                "Klik på <b>Åbn tastaturindstillingerne</b> herunder.",
                "Vælg <b>IBus Wayland</b> på listen, og klik på <b>Anvend</b>.",
            ]
        else:
            steps.append("Vælg <b>IBus</b> som indtastningsmetode i systemets indstillinger.")
        steps += [
            "Gem Ordhjælps indstillinger, hvis du har ændret noget.",
            "Klik på <b>Tjek igen</b>. Når alle punkter har et grønt flueben, er du klar.",
        ]
        return steps

    def open_settings(self) -> bool:
        if not _is_kde_wayland():
            return False
        for cmd in (["kcmshell6", KDE_KEYBOARD_KCM], ["systemsettings", KDE_KEYBOARD_KCM]):
            if shutil.which(cmd[0]) is None:
                continue
            try:
                subprocess.Popen(cmd, start_new_session=True)  # noqa: S603
            except OSError:
                continue
            return True
        return False
