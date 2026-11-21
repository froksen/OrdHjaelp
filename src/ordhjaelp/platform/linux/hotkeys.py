"""Globale genveje på Linux via xdg-desktop-portal (GlobalShortcuts).

Virker på Wayland (KDE Plasma 6, GNOME 48+ m.fl.). Brugeren godkender og
kan ændre genvejene i systemindstillingerne.
Spec: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from dbus_fast import Variant

from ordhjaelp.platform.linux.portal import Portal, new_token

log = logging.getLogger(__name__)

GS_IFACE = "org.freedesktop.portal.GlobalShortcuts"

DESCRIPTIONS = {
    "laes": "Læs markeret tekst op (tryk igen for at stoppe)",
    "stop": "Stop oplæsning",
    "dikter": "Diktér: start/stop optagelse",
}


class PortalHotkeys:
    def __init__(self) -> None:
        self._portal: Portal | None = None

    def start(self, bindings: dict[str, str], on_activated: Callable[[str], None]) -> None:
        portal = Portal.shared()
        self._portal = portal
        portal.on_signal(GS_IFACE, "Activated", lambda msg: on_activated(msg.body[1]))
        # Første gang venter dette på, at brugeren godkender i KDE/GNOME-dialogen.
        portal.run(self._bind(portal, bindings), timeout=310)

    def stop(self) -> None:
        if self._portal:
            self._portal.close()

    @staticmethod
    async def _bind(portal: Portal, bindings: dict[str, str]) -> None:
        session = await portal.create_session(GS_IFACE)
        shortcuts = [
            [
                action,
                {
                    "description": Variant("s", DESCRIPTIONS.get(action, action)),
                    "preferred_trigger": Variant("s", trigger),
                },
            ]
            for action, trigger in bindings.items()
        ]
        token = new_token()
        bound = await portal.request(
            GS_IFACE,
            "BindShortcuts",
            "oa(sa{sv})sa{sv}",
            [session, shortcuts, "", {"handle_token": Variant("s", token)}],
            token,
        )
        for sc_id, props in bound.get("shortcuts", Variant("a(sa{sv})", [])).value:
            trig = props.get("trigger_description")
            if trig and trig.value:
                log.info("Genvej %s: %s", sc_id, trig.value)
            else:
                log.warning(
                    "Genvejen '%s' fik ingen tast – måske bruges %s allerede af et andet "
                    "program. Vælg en tast under Systemindstillinger → Tastaturgenveje → Ordhjælp.",
                    sc_id,
                    bindings.get(sc_id),
                )
