"""Skriv tekst ind i det aktive program (Wayland, uden root).

Metode: teksten lægges i udklipsholderen, og der sendes Ctrl+V via
xdg-desktop-portal (RemoteDesktop). Bagefter lægges den tidligere tekst tilbage
i udklipsholderen.

Hvorfor ikke "taste" tegn for tegn? KDE's portal kan lade Shift hænge fast ved
store bogstaver (alt bliver skrevet med VERSALER), og tegn som ?, ! og € kræver
viden om tastaturlayoutet. Indsæt virker ens for alle tegn og er hurtigere.

Første gang spørger KDE/GNOME, om Ordhjælp må styre tastaturet; tilladelsen
huskes derefter (restore_token).
Spec: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import threading
import time

from dbus_fast import Variant

from ordhjaelp.config import data_dir
from ordhjaelp.platform.linux.portal import Portal, PortalError, new_token

log = logging.getLogger(__name__)

RD_IFACE = "org.freedesktop.portal.RemoteDesktop"
DEVICE_KEYBOARD = 1
PERSIST_UNTIL_REVOKED = 2

KEYSYM_CONTROL_L = 0xFFE3
KEYSYM_V = 0x76  # lille v – kræver ikke Shift

CLIPBOARD_SETTLE = 0.08  # vent til udklipsholderen er klar, før Ctrl+V
RESTORE_DELAY = 0.5  # vent til programmet har indsat, før gammel tekst lægges tilbage


def _token_path():
    return data_dir() / "remotedesktop.token"


def _read_clipboard() -> str | None:
    try:
        result = subprocess.run(
            ["wl-paste", "--no-newline", "--type", "text"],
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


def _write_clipboard(text: str) -> None:
    # wl-copy bliver kørende i baggrunden og leverer teksten, til noget andet kopieres.
    subprocess.run(
        ["wl-copy", "--type", "text/plain;charset=utf-8"], input=text.encode(), timeout=2
    )


class PortalKeyboard:
    def __init__(self) -> None:
        self._portal = Portal.shared()
        self._session: str | None = None
        self._lock = threading.Lock()

    def insert(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            previous = _read_clipboard()
            _write_clipboard(text)
            time.sleep(CLIPBOARD_SETTLE)
            try:
                self._portal.run(self._paste(), timeout=310)
            except PortalError as exc:
                # Sessionen kan være lukket (fx efter dvale) – prøv én gang mere.
                log.info("Genstarter tastatur-session (%s)", exc)
                self._session = None
                self._portal.run(self._paste(), timeout=310)
            finally:
                if previous is not None:
                    threading.Timer(RESTORE_DELAY, _write_clipboard, (previous,)).start()

    async def _paste(self) -> None:
        if self._session is None:
            self._session = await self._start_session()
        for sym, state in (
            (KEYSYM_CONTROL_L, 1),
            (KEYSYM_V, 1),
            (KEYSYM_V, 0),
            (KEYSYM_CONTROL_L, 0),
        ):
            await self._portal.call(
                RD_IFACE, "NotifyKeyboardKeysym", "oa{sv}iu", [self._session, {}, sym, state]
            )
            await asyncio.sleep(0.01)

    async def _start_session(self) -> str:
        portal = self._portal
        session = await portal.create_session(RD_IFACE)

        options = {
            "types": Variant("u", DEVICE_KEYBOARD),
            "persist_mode": Variant("u", PERSIST_UNTIL_REVOKED),
        }
        path = _token_path()
        if path.exists():
            options["restore_token"] = Variant("s", path.read_text().strip())
        token = new_token()
        options["handle_token"] = Variant("s", token)
        await portal.request(RD_IFACE, "SelectDevices", "oa{sv}", [session, options], token)

        token = new_token()
        results = await portal.request(
            RD_IFACE,
            "Start",
            "osa{sv}",
            [session, "", {"handle_token": Variant("s", token)}],
            token,
        )
        if not results.get("devices", Variant("u", 0)).value & DEVICE_KEYBOARD:
            raise PortalError("Tastaturadgang blev ikke givet")
        if "restore_token" in results:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(results["restore_token"].value)
        log.info("Tastatur-adgang via portal er klar")
        return session
