"""Globale genveje på Linux via xdg-desktop-portal (GlobalShortcuts).

Virker på Wayland (KDE Plasma 6, GNOME 48+ m.fl.). Brugeren godkender og
kan ændre genvejene i systemindstillingerne.
Spec: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from collections.abc import Callable

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus

from ordhjaelp.config import APP_ID

log = logging.getLogger(__name__)

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
GS_IFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_IFACE = "org.freedesktop.portal.Request"
REGISTRY_IFACE = "org.freedesktop.host.portal.Registry"

DESCRIPTIONS = {
    "laes": "Læs markeret tekst op (tryk igen for at stoppe)",
    "stop": "Stop oplæsning",
}


class PortalError(RuntimeError):
    pass


class PortalHotkeys:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bus: MessageBus | None = None
        self._pending: dict[str, asyncio.Future[tuple[int, dict]]] = {}
        self._ready = threading.Event()
        self._error: BaseException | None = None

    # -- offentlig API -------------------------------------------------
    def start(self, bindings: dict[str, str], on_activated: Callable[[str], None]) -> None:
        self._thread = threading.Thread(
            target=self._thread_main,
            args=(bindings, on_activated),
            daemon=True,
            name="portal-hotkeys",
        )
        self._thread.start()
        self._ready.wait(timeout=60)
        if self._error:
            raise PortalError(str(self._error)) from self._error

    def stop(self) -> None:
        if self._loop and self._bus:
            self._loop.call_soon_threadsafe(self._bus.disconnect)

    # -- intern --------------------------------------------------------
    def _thread_main(self, bindings: dict[str, str], cb: Callable[[str], None]) -> None:
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._run(bindings, cb))
        except BaseException as exc:  # noqa: BLE001 - rapporteres til start()
            self._error = exc
            self._ready.set()

    async def _run(self, bindings: dict[str, str], cb: Callable[[str], None]) -> None:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._bus = bus
        sender = bus.unique_name.lstrip(":").replace(".", "_")

        def handler(msg: Message) -> None:
            if msg.message_type != MessageType.SIGNAL:
                return
            if msg.interface == REQUEST_IFACE and msg.member == "Response":
                fut = self._pending.pop(msg.path, None)
                if fut and not fut.done():
                    fut.set_result((msg.body[0], msg.body[1]))
            elif msg.interface == GS_IFACE and msg.member == "Activated":
                shortcut_id = msg.body[1]
                try:
                    cb(shortcut_id)
                except Exception:
                    log.exception("Fejl ved håndtering af genvej %s", shortcut_id)

        bus.add_message_handler(handler)
        for rule in (
            f"type='signal',interface='{REQUEST_IFACE}',member='Response'",
            f"type='signal',interface='{GS_IFACE}',member='Activated'",
        ):
            await self._call(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "AddMatch",
                "s",
                [rule],
            )

        # Fortæl portalen hvilken app vi er (ikke-sandboxede apps, portal >= 1.19).
        try:
            await self._call(
                PORTAL_BUS, PORTAL_PATH, REGISTRY_IFACE, "Register", "sa{sv}", [APP_ID, {}]
            )
        except PortalError as exc:
            log.debug("Registry.Register ikke tilgængelig: %s", exc)

        # 1) Opret session
        token = self._token()
        results = await self._request(
            sender,
            token,
            "CreateSession",
            "a{sv}",
            [
                {
                    "handle_token": Variant("s", token),
                    "session_handle_token": Variant("s", self._token()),
                }
            ],
        )
        session = results["session_handle"].value

        # 2) Bind genveje (KDE/GNOME viser evt. en godkendelsesdialog første gang)
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
        token = self._token()
        bound = await self._request(
            sender,
            token,
            "BindShortcuts",
            "oa(sa{sv})sa{sv}",
            [session, shortcuts, "", {"handle_token": Variant("s", token)}],
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

        self._ready.set()
        await bus.wait_for_disconnect()

    async def _request(self, sender: str, token: str, method: str, sig: str, body: list) -> dict:
        path = f"{PORTAL_PATH}/request/{sender}/{token}"
        fut: asyncio.Future[tuple[int, dict]] = asyncio.get_running_loop().create_future()
        self._pending[path] = fut
        await self._call(PORTAL_BUS, PORTAL_PATH, GS_IFACE, method, sig, body)
        code, results = await asyncio.wait_for(fut, timeout=300)
        if code != 0:
            raise PortalError(f"{method} blev afvist eller annulleret (kode {code})")
        return results

    async def _call(
        self, dest: str, path: str, iface: str, member: str, sig: str, body: list
    ) -> list:
        assert self._bus is not None
        reply = await self._bus.call(
            Message(
                destination=dest,
                path=path,
                interface=iface,
                member=member,
                signature=sig,
                body=body,
            )
        )
        if reply is None or reply.message_type == MessageType.ERROR:
            err = reply.body[0] if reply and reply.body else "ukendt fejl"
            raise PortalError(f"{iface}.{member}: {reply.error_name if reply else ''} {err}")
        return reply.body

    @staticmethod
    def _token() -> str:
        return "ordhjaelp_" + secrets.token_hex(6)
