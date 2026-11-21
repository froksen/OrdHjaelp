"""Skærmbillede på Linux via xdg-desktop-portal (Screenshot).

Virker på Wayland. Første gang kan KDE/GNOME spørge om lov.
Spec: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

from dbus_fast import Variant

from ordhjaelp.platform.linux.portal import Portal, PortalError, new_token

log = logging.getLogger(__name__)

SCREENSHOT_IFACE = "org.freedesktop.portal.Screenshot"


class PortalScreenshot:
    def __init__(self) -> None:
        self._portal = Portal.shared()

    def capture(self) -> bytes:
        return self._portal.run(self._capture(), timeout=120)

    async def _capture(self) -> bytes:
        token = new_token()
        results = await self._portal.request(
            SCREENSHOT_IFACE,
            "Screenshot",
            "sa{sv}",
            ["", {"handle_token": Variant("s", token), "interactive": Variant("b", False)}],
            token,
        )
        uri = results.get("uri")
        if uri is None:
            raise PortalError("Portalen returnerede intet billede")
        path = Path(unquote(urlparse(uri.value).path))
        try:
            return path.read_bytes()
        finally:
            # Billedet er kun til os – lad det ikke ligge og fylde (fx i Billeder-mappen).
            with contextlib.suppress(OSError):
                path.unlink()
