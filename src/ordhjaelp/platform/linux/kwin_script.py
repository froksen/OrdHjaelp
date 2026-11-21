"""Kør et lille JavaScript i KWin (KDE Plasma) og få svaret tilbage over D-Bus.

På Wayland må almindelige programmer hverken se musen eller flytte deres egne
vinduer. KWin (KDE's vindueshåndtering) må godt, og den kan køre små scripts.
Scriptet svarer ved at kalde Report på vores D-Bus-forbindelse.

NB: Filen bruger bevidst ikke `from __future__ import annotations`, fordi dbus-fast
læser D-Bus-typerne ("s") direkte fra annotationerne.
"""

import asyncio
import contextlib
import json
import secrets
import tempfile
from collections.abc import Callable
from pathlib import Path

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method

RECEIVER_PATH = "/dk/ordhjaelp/KWin"
RECEIVER_IFACE = "dk.ordhjaelp.KWin"
TIMEOUT = 3.0


def report_call(service: str) -> str:
    """JavaScript-starten på kaldet, der sender svaret tilbage: callDBus(…, "Report","""
    names = ", ".join(json.dumps(x) for x in (service, RECEIVER_PATH, RECEIVER_IFACE))
    return f'callDBus({names}, "Report", '


class _Receiver(ServiceInterface):
    def __init__(self, future: asyncio.Future) -> None:
        super().__init__(RECEIVER_IFACE)
        self._future = future

    @method()
    def Report(self, data: "s"):  # noqa: F821, N802, ANN201 - D-Bus-metode kaldt af KWin
        if not self._future.done():
            self._future.set_result(data)


async def _call(bus: MessageBus, path: str, iface: str, member: str, sig: str, body: list) -> list:
    reply = await bus.call(
        Message(
            destination="org.kde.KWin",
            path=path,
            interface=iface,
            member=member,
            signature=sig,
            body=body,
        )
    )
    if reply is None or reply.message_type == MessageType.ERROR:
        err = reply.body[0] if reply and reply.body else ""
        raise RuntimeError(f"KWin {member}: {err}")
    return reply.body


async def run_script(make_source: Callable[[str], str], name: str) -> str:
    """Kør scriptet, vent på dets Report, og fjern det igen.

    :param make_source: laver scriptets tekst ud fra vores D-Bus-navn (se report_call).
    :param name: kort navn til KWin, fx "mus". Gøres unikt her.
    """
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    bus.export(RECEIVER_PATH, _Receiver(future))
    plugin = f"ordhjaelp-{name}-{secrets.token_hex(4)}"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(make_source(bus.unique_name))
        script_path = Path(f.name)
    try:
        (script_id,) = await _call(
            bus, "/Scripting", "org.kde.kwin.Scripting", "loadScript", "ss",
            [str(script_path), plugin],
        )  # fmt: skip
        await _call(bus, f"/Scripting/Script{script_id}", "org.kde.kwin.Script", "run", "", [])
        return await asyncio.wait_for(future, TIMEOUT)
    finally:
        with contextlib.suppress(Exception):
            await _call(bus, "/Scripting", "org.kde.kwin.Scripting", "unloadScript", "s", [plugin])
        script_path.unlink(missing_ok=True)
        bus.disconnect()


async def available() -> bool:
    """Kører KWin (KDE Plasma)?"""
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        reply = await bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="NameHasOwner",
                signature="s",
                body=["org.kde.KWin"],
            )
        )
        return bool(reply and reply.message_type != MessageType.ERROR and reply.body[0])
    finally:
        bus.disconnect()
