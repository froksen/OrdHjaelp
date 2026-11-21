"""Fælles forbindelse til xdg-desktop-portal (Wayland-venlig adgang til skrivebordet).

Alle portal-funktioner (genveje, tastatur, skærmbilleder …) deler én D-Bus-
forbindelse, der kører i sin egen tråd med sin egen asyncio-løkke.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus

from ordhjaelp.config import APP_ID

log = logging.getLogger(__name__)

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
REQUEST_IFACE = "org.freedesktop.portal.Request"
REGISTRY_IFACE = "org.freedesktop.host.portal.Registry"

SignalHandler = Callable[[Message], None]


class PortalError(RuntimeError):
    pass


class Portal:
    _shared: Portal | None = None
    _shared_lock = threading.Lock()

    @classmethod
    def shared(cls) -> Portal:
        with cls._shared_lock:
            if cls._shared is None:
                cls._shared = Portal()
            return cls._shared

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._pending: dict[str, asyncio.Future[tuple[int, dict]]] = {}
        self._signal_handlers: dict[tuple[str, str], list[SignalHandler]] = {}
        threading.Thread(target=self._loop.run_forever, daemon=True, name="portal").start()
        self._bus: MessageBus = self.run(self._connect(), timeout=10)
        self._sender = self._bus.unique_name.lstrip(":").replace(".", "_")

    # -- bruges fra andre tråde -----------------------------------------
    def run(self, coro: Coroutine[Any, Any, Any], timeout: float | None = None) -> Any:
        """Kør en coroutine i portal-tråden og vent på resultatet."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def on_signal(self, interface: str, member: str, handler: SignalHandler) -> None:
        self._signal_handlers.setdefault((interface, member), []).append(handler)
        self.run(self._add_match(f"type='signal',interface='{interface}',member='{member}'"))

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._bus.disconnect)

    # -- coroutines (kører i portal-tråden) -----------------------------
    async def call(
        self,
        interface: str,
        member: str,
        signature: str,
        body: list,
        destination: str = PORTAL_BUS,
        path: str = PORTAL_PATH,
    ) -> list:
        reply = await self._bus.call(
            Message(
                destination=destination,
                path=path,
                interface=interface,
                member=member,
                signature=signature,
                body=body,
            )
        )
        if reply is None or reply.message_type == MessageType.ERROR:
            err = reply.body[0] if reply and reply.body else "ukendt fejl"
            name = reply.error_name if reply else ""
            raise PortalError(f"{interface}.{member}: {name} {err}")
        return reply.body

    async def request(
        self, interface: str, method: str, signature: str, body: list, token: str
    ) -> dict:
        """Kald en portal-metode, der svarer asynkront via et Request-objekt.

        `token` skal være den handle_token, der er sat i kaldets options.
        """
        path = f"{PORTAL_PATH}/request/{self._sender}/{token}"
        fut: asyncio.Future[tuple[int, dict]] = self._loop.create_future()
        self._pending[path] = fut
        try:
            await self.call(interface, method, signature, body)
            code, results = await asyncio.wait_for(fut, timeout=300)
        finally:
            self._pending.pop(path, None)
        if code != 0:
            raise PortalError(f"{method} blev afvist eller annulleret (kode {code})")
        return results

    async def create_session(self, interface: str) -> str:
        token = new_token()
        results = await self.request(
            interface,
            "CreateSession",
            "a{sv}",
            [
                {
                    "handle_token": Variant("s", token),
                    "session_handle_token": Variant("s", new_token()),
                }
            ],
            token,
        )
        return results["session_handle"].value

    # -- intern ---------------------------------------------------------
    async def _connect(self) -> MessageBus:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._bus = bus
        bus.add_message_handler(self._dispatch)
        await self._add_match(f"type='signal',interface='{REQUEST_IFACE}',member='Response'")
        # Fortæl portalen hvilken app vi er (ikke-sandboxede apps, portal >= 1.19).
        # Kræver at .desktop-filen er installeret ('ordhjaelp installer').
        try:
            await self.call(REGISTRY_IFACE, "Register", "sa{sv}", [APP_ID, {}])
        except PortalError as exc:
            log.debug("Registry.Register ikke tilgængelig: %s", exc)
        return bus

    async def _add_match(self, rule: str) -> None:
        await self.call(
            "org.freedesktop.DBus",
            "AddMatch",
            "s",
            [rule],
            destination="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
        )

    def _dispatch(self, msg: Message) -> None:
        if msg.message_type != MessageType.SIGNAL:
            return
        if msg.interface == REQUEST_IFACE and msg.member == "Response":
            fut = self._pending.get(msg.path)
            if fut and not fut.done():
                fut.set_result((msg.body[0], msg.body[1]))
            return
        for handler in self._signal_handlers.get((msg.interface, msg.member), []):
            try:
                handler(msg)
            except Exception:
                log.exception("Fejl i håndtering af %s.%s", msg.interface, msg.member)


def new_token() -> str:
    return "ordhjaelp_" + secrets.token_hex(6)
