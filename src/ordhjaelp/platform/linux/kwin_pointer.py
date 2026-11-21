"""Musens position og vinduet under den på KDE Plasma (Wayland) via et lille KWin-script.

På Wayland må almindelige programmer ikke se, hvor musen er. KWin (KDE's
vindueshåndtering) ved det, og den kan køre små JavaScript-filer. Scriptet
sender svaret tilbage til os over D-Bus.

NB: Filen bruger bevidst ikke `from __future__ import annotations`, fordi dbus-fast
læser D-Bus-typerne ("s") direkte fra annotationerne.
"""

import asyncio
import contextlib
import json
import logging
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method

log = logging.getLogger(__name__)

RECEIVER_PATH = "/dk/ordhjaelp/Pointer"
RECEIVER_IFACE = "dk.ordhjaelp.Pointer"
TIMEOUT = 3.0

# Gennemgår vinduerne oppefra og finder det øverste, som musen står over.
SCRIPT = """\
(function () {
  var pos = workspace.cursorPos;
  var found = {x: pos.x, y: pos.y, pid: 0, caption: "", clientX: 0, clientY: 0};
  var wins = workspace.stackingOrder;
  for (var i = wins.length - 1; i >= 0; i--) {
    var w = wins[i];
    try {
      if (w.minimized || w.deleted) continue;
      if (!w.onAllDesktops && w.desktops && w.desktops.indexOf(workspace.currentDesktop) < 0)
        continue;
      var g = w.frameGeometry;
      if (pos.x < g.x || pos.y < g.y || pos.x >= g.x + g.width || pos.y >= g.y + g.height)
        continue;
      var c = w.clientGeometry;
      found.pid = w.pid; found.caption = w.caption; found.clientX = c.x; found.clientY = c.y;
      break;
    } catch (e) {}
  }
  callDBus(%(service)s, %(path)s, %(iface)s, "Report", JSON.stringify(found));
})();
"""


@dataclass(frozen=True)
class PointerInfo:
    x: int
    y: int
    pid: int = 0
    caption: str = ""
    client_x: int = 0
    client_y: int = 0

    @property
    def window_x(self) -> int:
        return self.x - self.client_x

    @property
    def window_y(self) -> int:
        return self.y - self.client_y


def make_script(service: str) -> str:
    return SCRIPT % {
        "service": json.dumps(service),
        "path": json.dumps(RECEIVER_PATH),
        "iface": json.dumps(RECEIVER_IFACE),
    }


def parse_report(data: str) -> PointerInfo:
    raw = json.loads(data)
    return PointerInfo(
        x=round(float(raw.get("x", 0))),
        y=round(float(raw.get("y", 0))),
        pid=int(raw.get("pid") or 0),
        caption=str(raw.get("caption") or ""),
        client_x=round(float(raw.get("clientX", 0))),
        client_y=round(float(raw.get("clientY", 0))),
    )


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


async def locate() -> PointerInfo:
    """Spørg KWin, hvor musen er, og hvilket vindue den står over."""
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    bus.export(RECEIVER_PATH, _Receiver(future))
    plugin = f"ordhjaelp-mus-{secrets.token_hex(4)}"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(make_script(bus.unique_name))
        script_path = Path(f.name)
    try:
        (script_id,) = await _call(
            bus, "/Scripting", "org.kde.kwin.Scripting", "loadScript", "ss",
            [str(script_path), plugin],
        )  # fmt: skip
        await _call(bus, f"/Scripting/Script{script_id}", "org.kde.kwin.Script", "run", "", [])
        return parse_report(await asyncio.wait_for(future, TIMEOUT))
    finally:
        with contextlib.suppress(Exception):
            await _call(bus, "/Scripting", "org.kde.kwin.Scripting", "unloadScript", "s", [plugin])
        script_path.unlink(missing_ok=True)
        bus.disconnect()


async def available() -> bool:
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
