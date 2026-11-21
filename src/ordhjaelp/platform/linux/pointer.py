"""Læs under musen på Linux: find musens position og teksten under den.

Wayland (KDE Plasma): musens position og vinduet under den hentes fra KWin,
og teksten findes med AT-SPI i vinduets egne koordinater.
X11: musens position hentes med xdotool, og AT-SPI bruges med skærmkoordinater.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess

from ordhjaelp.platform.linux import atspi, kwin_pointer
from ordhjaelp.platform.linux.selection import _session_type
from ordhjaelp.services.pointer_read import extract

log = logging.getLogger(__name__)


def _x11_pointer() -> tuple[int, int] | None:
    if shutil.which("xdotool") is None:
        log.warning("Læs under musen kræver xdotool på X11: sudo dnf install xdotool")
        return None
    result = subprocess.run(
        ["xdotool", "getmouselocation", "--shell"],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    try:
        return int(values["X"]), int(values["Y"])
    except (KeyError, ValueError):
        return None


class LinuxPointerText:
    def prepare(self) -> None:
        """Bed programmerne om at slå tilgængelighed til. Kaldes én gang ved start."""
        try:
            asyncio.run(atspi.enable_accessibility())
        except Exception as exc:  # noqa: BLE001
            log.warning("Kunne ikke slå tilgængelighed til: %s", exc)

    def text_at_pointer(self, unit: str) -> str | None:
        """Kaldes fra en almindelig tråd (ikke fra en kørende asyncio-løkke)."""
        return asyncio.run(self._lookup(unit))

    async def _lookup(self, unit: str) -> str | None:
        with_following = unit == "herfra"
        bus = await atspi.connect()
        try:
            api = atspi.Atspi(bus)
            if _session_type() == "wayland":
                if not await kwin_pointer.available():
                    log.warning("Læs under musen kræver KDE Plasma (KWin) på Wayland")
                    return None
                info = await kwin_pointer.locate()
                log.debug("Musen: %s", info)
                frame = await api.frame_for_window(info.pid, info.caption)
                if frame is None:
                    return None
                hit = await api.text_at_point(
                    frame, info.window_x, info.window_y, atspi.COORD_WINDOW, with_following
                )
            else:
                pos = _x11_pointer()
                if pos is None:
                    return None
                frame = await api.frame_at_screen_point(*pos)
                if frame is None:
                    return None
                hit = await api.text_at_point(frame, *pos, atspi.COORD_SCREEN, with_following)
        finally:
            bus.disconnect()
        if hit is None:
            return None
        text = extract(hit.text, hit.offset, unit)
        if with_following and hit.following:
            text = " ".join([text, *hit.following])
            text = extract(text, 0, unit)  # samme loft over længden
        return text or None
