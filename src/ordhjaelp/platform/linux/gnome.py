"""Ikoner ved uret på GNOME.

GNOME viser ikke ikoner ved uret af sig selv. Det kræver udvidelsen
"AppIndicator and KStatusNotifierItem Support". Ordhjælp kan se, om udvidelsen
er installeret, og slå den til, men ikke installere den (det kræver sudo).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time

log = logging.getLogger(__name__)

# Fedora og GNOME's egen udgave har samme id. Ubuntu har sin egen udgave.
UUIDS = ("appindicatorsupport@rgcjonas.gmail.com", "ubuntu-appindicators@ubuntu.com")
PACKAGE = "gnome-shell-extension-appindicator"  # samme navn i Fedora og Debian/Ubuntu
WATCHER = "org.kde.StatusNotifierWatcher"  # findes på D-Bus, når udvidelsen kører

MISSING = "mangler"
DISABLED = "slået fra"
ENABLED = "slået til"


def is_gnome() -> bool:
    return "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str] | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _extensions(enabled: bool) -> set[str]:
    result = _run(["gnome-extensions", "list", *(["--enabled"] if enabled else [])])
    if result is None or result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _watcher_running() -> bool:
    result = _run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.freedesktop.DBus",
            "--object-path",
            "/org/freedesktop/DBus",
            "--method",
            "org.freedesktop.DBus.NameHasOwner",
            WATCHER,
        ]
    )
    return result is not None and "true" in result.stdout


class AppIndicatorExtension:
    name = "AppIndicator and KStatusNotifierItem Support"

    @property
    def install_command(self) -> str:
        tool = "apt" if shutil.which("apt") and not shutil.which("dnf") else "dnf"
        return f"sudo {tool} install {PACKAGE}"

    def _installed_uuid(self) -> str | None:
        installed = _extensions(enabled=False)
        return next((uuid for uuid in UUIDS if uuid in installed), None)

    def state(self) -> str:
        uuid = self._installed_uuid()
        if uuid is None:
            return MISSING
        return ENABLED if uuid in _extensions(enabled=True) else DISABLED

    def enable(self) -> bool:
        uuid = self._installed_uuid()
        if uuid is None:
            return False
        result = _run(["gnome-extensions", "enable", uuid])
        if result is None or result.returncode != 0:
            log.warning("Kunne ikke slå %s til: %s", uuid, result.stderr if result else "")
            return False
        return True

    def wait_until_ready(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            if _watcher_running():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.25)
