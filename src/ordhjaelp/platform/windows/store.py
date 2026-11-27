"""Ordhjælp som MSIX-pakke (Microsoft Store).

En MSIX-pakke er installeret anderledes end med Setup.exe:

* Start ved login kan ikke skrives i registreringsdatabasen (HKCU\\...\\Run): Windows
  omdirigerer pakkens skrivninger dertil. Pakken har i stedet en "StartupTask" i sit
  manifest (packaging/windows/store/AppxManifest.xml.in), som slås til og fra her.
* Windows og Microsoft Store installerer og afinstallerer, så kommandoerne
  "installer" og "afinstaller" bruges ikke.

Modulet kan importeres på Linux: Windows' DLL og WinRT indlæses først ved brug.
"""

from __future__ import annotations

import enum
import functools
import logging
import sys
import threading
from collections.abc import Callable, Coroutine
from typing import Any, Protocol

log = logging.getLogger(__name__)

# Skal passe med TaskId i AppxManifest.xml.in
STARTUP_TASK_ID = "OrdhjaelpStart"

ERROR_INSUFFICIENT_BUFFER = 122
APPMODEL_ERROR_NO_PACKAGE = 15700

BLOCKED_BY_USER = (
    "Start ved login er slået fra i Windows' indstillinger. Slå det til under\n"
    "Indstillinger → Apps → Start."
)
BLOCKED_BY_POLICY = "Start ved login er slået fra af skolens eller computerens administrator."


class StartupState(enum.IntEnum):
    """Samme tal som Windows.ApplicationModel.StartupTaskState."""

    DISABLED = 0
    DISABLED_BY_USER = 1
    ENABLED = 2
    DISABLED_BY_POLICY = 3
    ENABLED_BY_POLICY = 4


ENABLED_STATES = (StartupState.ENABLED, StartupState.ENABLED_BY_POLICY)


def is_packaged(get_full_name: Callable[[], int] | None = None) -> bool:
    """Kører Ordhjælp fra en MSIX-pakke (fx installeret fra Microsoft Store)?"""
    if get_full_name is None:
        if sys.platform != "win32":
            return False
        return _is_packaged_cached()
    return get_full_name() != APPMODEL_ERROR_NO_PACKAGE


@functools.cache
def _is_packaged_cached() -> bool:
    return is_packaged(_package_full_name_status)


def _package_full_name_status() -> int:
    """GetCurrentPackageFullName med en tom buffer: fejlkoden siger, om der er en pakke."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32")
    get_name = getattr(kernel32, "GetCurrentPackageFullName", None)
    if get_name is None:  # meget gammel Windows: ingen pakker
        return APPMODEL_ERROR_NO_PACKAGE
    length = wintypes.UINT(0)
    return int(get_name(ctypes.byref(length), None))


class StartupTasks(Protocol):
    """Den del af WinRT's StartupTask, Ordhjælp bruger (kan erstattes i tests)."""

    def state(self) -> StartupState: ...
    def request_enable(self) -> StartupState: ...
    def disable(self) -> None: ...


class StoreAutostart:
    """Start ved login for MSIX-pakken via dens StartupTask."""

    def __init__(self, tasks: StartupTasks | None = None) -> None:
        self._tasks = tasks or WinRTStartupTask()

    def is_enabled(self) -> bool:
        return self._tasks.state() in ENABLED_STATES

    def set_enabled(self, enabled: bool) -> None:
        if not enabled:
            if self._tasks.state() != StartupState.ENABLED_BY_POLICY:
                self._tasks.disable()
            return
        state = self._tasks.request_enable()
        if state == StartupState.DISABLED_BY_USER:
            raise OSError(BLOCKED_BY_USER)  # kun brugeren kan slå det til igen
        if state == StartupState.DISABLED_BY_POLICY:
            raise OSError(BLOCKED_BY_POLICY)


def _run(coroutine: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
    """Kør en WinRT-coroutine i en egen tråd (kalderen kan have en asyncio-løkke)."""
    import asyncio

    result: dict[str, Any] = {}

    def work() -> None:
        try:
            result["value"] = asyncio.run(coroutine())
        except BaseException as exc:  # noqa: BLE001 - sendes videre til kalderen
            result["error"] = exc

    thread = threading.Thread(target=work, name="startup-task", daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise OSError(f"StartupTask fejlede: {result['error']}") from result["error"]
    return result.get("value")


class WinRTStartupTask:
    """Windows.ApplicationModel.StartupTask via pywinrt (kun i MSIX-pakken)."""

    def _task(self):  # noqa: ANN202
        from winrt.windows.applicationmodel import StartupTask

        return StartupTask.get_async(STARTUP_TASK_ID)

    def state(self) -> StartupState:
        async def get() -> int:
            return int((await self._task()).state)

        return StartupState(_run(get))

    def request_enable(self) -> StartupState:
        async def enable() -> int:
            return int(await (await self._task()).request_enable_async())

        return StartupState(_run(enable))

    def disable(self) -> None:
        async def off() -> None:
            (await self._task()).disable()

        _run(off)
