"""Tekst under et punkt på skærmen via AT-SPI (Linux' tilgængeligheds-API).

Det er den samme API, som skærmlæseren Orca bruger. Programmer som Firefox,
LibreOffice og GTK/Qt-programmer fortæller her, hvilken tekst der står hvor.
Vi taler direkte D-Bus med dbus-fast, så der ikke skal bruges flere pakker.

Spec: https://gnome.pages.gitlab.gnome.org/at-spi2-core/devel-docs/
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus

log = logging.getLogger(__name__)

ACCESSIBLE = "org.a11y.atspi.Accessible"
COMPONENT = "org.a11y.atspi.Component"
TEXT = "org.a11y.atspi.Text"
PROPERTIES = "org.freedesktop.DBus.Properties"
REGISTRY = "org.a11y.atspi.Registry"
ROOT_PATH = "/org/a11y/atspi/accessible/root"
NULL_PATH = "/org/a11y/atspi/null"

COORD_SCREEN = 0
COORD_WINDOW = 1

STATE_ACTIVE = 1
STATE_SHOWING = 25

MAX_DEPTH = 60
MAX_SIBLINGS = 200

# Dele af et vindue, hvor der aldrig er markeret tekst, man vil have læst op
_SKIP_ROLES = {"menu bar", "menu", "popup menu", "tool bar", "status bar", "scroll bar", "ruler"}


class AtspiError(RuntimeError):
    pass


@dataclass(frozen=True)
class Ref:
    """Et objekt i et program: (D-Bus-navn, sti)."""

    bus_name: str
    path: str

    @property
    def is_null(self) -> bool:
        return not self.bus_name or self.path == NULL_PATH


@dataclass(frozen=True)
class TextHit:
    """Teksten i objektet under musen og tegnet, musen står på."""

    text: str
    offset: int
    # Tekst fra de efterfølgende afsnit (til "læs herfra")
    following: tuple[str, ...] = ()


def _has_state(states: list[int], state: int) -> bool:
    word, bit = divmod(state, 32)
    return word < len(states) and bool(states[word] & (1 << bit))


async def connect() -> MessageBus:
    """Forbind til tilgængelighedsbussen (en særskilt D-Bus ved siden af sessionsbussen)."""
    session = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        reply = await session.call(
            Message(
                destination="org.a11y.Bus",
                path="/org/a11y/bus",
                interface="org.a11y.Bus",
                member="GetAddress",
            )
        )
    finally:
        session.disconnect()
    if reply is None or reply.message_type == MessageType.ERROR:
        raise AtspiError("Tilgængelighedsbussen (at-spi) kører ikke")
    return await MessageBus(bus_address=reply.body[0]).connect()


async def enable_accessibility() -> None:
    """Bed programmerne om at slå tilgængelighed til (Qt og Chromium gør det kun på opfordring)."""
    session = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        await session.call(
            Message(
                destination="org.a11y.Bus",
                path="/org/a11y/bus",
                interface=PROPERTIES,
                member="Set",
                signature="ssv",
                body=["org.a11y.Status", "IsEnabled", Variant("b", True)],
            )
        )
    finally:
        session.disconnect()


class Atspi:
    def __init__(self, bus: MessageBus) -> None:
        self._bus = bus

    async def _call(
        self, ref: Ref, interface: str, member: str, signature: str = "", body: list | None = None
    ) -> list:
        reply = await self._bus.call(
            Message(
                destination=ref.bus_name,
                path=ref.path,
                interface=interface,
                member=member,
                signature=signature,
                body=body or [],
            )
        )
        if reply is None or reply.message_type == MessageType.ERROR:
            err = reply.body[0] if reply and reply.body else ""
            raise AtspiError(f"{interface}.{member}: {err}")
        return reply.body

    async def _prop(self, ref: Ref, interface: str, name: str):  # noqa: ANN202
        (value,) = await self._call(ref, PROPERTIES, "Get", "ss", [interface, name])
        return value.value

    # -- træet ----------------------------------------------------------
    async def applications(self) -> list[Ref]:
        root = Ref(REGISTRY, ROOT_PATH)
        (children,) = await self._call(root, ACCESSIBLE, "GetChildren")
        return [Ref(name, path) for name, path in children]

    async def children(self, ref: Ref) -> list[Ref]:
        (children,) = await self._call(ref, ACCESSIBLE, "GetChildren")
        return [Ref(name, path) for name, path in children]

    async def pid(self, app: Ref) -> int | None:
        reply = await self._bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="GetConnectionUnixProcessID",
                signature="s",
                body=[app.bus_name],
            )
        )
        if reply is None or reply.message_type == MessageType.ERROR:
            return None
        return int(reply.body[0])

    async def name(self, ref: Ref) -> str:
        return str(await self._prop(ref, ACCESSIBLE, "Name"))

    async def states(self, ref: Ref) -> list[int]:
        (states,) = await self._call(ref, ACCESSIBLE, "GetState")
        return list(states)

    async def interfaces(self, ref: Ref) -> list[str]:
        (names,) = await self._call(ref, ACCESSIBLE, "GetInterfaces")
        return list(names)

    async def parent(self, ref: Ref) -> Ref:
        name, path = await self._prop(ref, ACCESSIBLE, "Parent")
        return Ref(name, path)

    async def index_in_parent(self, ref: Ref) -> int:
        (index,) = await self._call(ref, ACCESSIBLE, "GetIndexInParent")
        return int(index)

    async def contains(self, ref: Ref, x: int, y: int, coord: int) -> bool:
        (inside,) = await self._call(ref, COMPONENT, "Contains", "iiu", [x, y, coord])
        return bool(inside)

    async def child_at_point(self, ref: Ref, x: int, y: int, coord: int) -> Ref:
        ((name, path),) = await self._call(
            ref, COMPONENT, "GetAccessibleAtPoint", "iiu", [x, y, coord]
        )
        return Ref(name, path)

    async def full_text(self, ref: Ref) -> str:
        (text,) = await self._call(ref, TEXT, "GetText", "ii", [0, -1])
        return str(text)

    async def offset_at_point(self, ref: Ref, x: int, y: int, coord: int) -> int:
        (offset,) = await self._call(ref, TEXT, "GetOffsetAtPoint", "iiu", [x, y, coord])
        return int(offset)

    # -- at finde vinduet -------------------------------------------------
    async def frames(self, app: Ref) -> list[Ref]:
        try:
            return await self.children(app)
        except AtspiError:
            return []

    async def frame_for_window(self, pid: int, caption: str) -> Ref | None:
        """Wayland: find programmets vindue ud fra proces-id og vinduestitel (fra KWin)."""
        apps = await self.applications()
        matching = [app for app in apps if pid and await self.pid(app) == pid]
        for app in matching or apps:  # sandboxede programmer har et andet proces-id
            frames = await self.frames(app)
            for frame in frames:
                if caption and await self._safe_name(frame) == caption:
                    return frame
            if matching:
                for frame in frames:
                    if _has_state(await self._safe_states(frame), STATE_ACTIVE):
                        return frame
                if frames:
                    return frames[0]
        return None

    async def frame_at_screen_point(self, x: int, y: int) -> Ref | None:
        """X11: find det vindue, der indeholder punktet (skærmkoordinater virker her)."""
        hits: list[tuple[bool, Ref]] = []
        for app in await self.applications():
            for frame in await self.frames(app):
                states = await self._safe_states(frame)
                if not _has_state(states, STATE_SHOWING):
                    continue
                try:
                    if await self.contains(frame, x, y, COORD_SCREEN):
                        hits.append((_has_state(states, STATE_ACTIVE), frame))
                except AtspiError:
                    continue
        if not hits:
            return None
        hits.sort(key=lambda hit: not hit[0])  # det aktive vindue først
        return hits[0][1]

    async def _safe_name(self, ref: Ref) -> str:
        try:
            return await self.name(ref)
        except AtspiError:
            return ""

    async def _safe_states(self, ref: Ref) -> list[int]:
        try:
            return await self.states(ref)
        except AtspiError:
            return []

    # -- teksten under punktet ------------------------------------------
    async def text_at_point(
        self, frame: Ref, x: int, y: int, coord: int, with_following: bool = False
    ) -> TextHit | None:
        """Gå ned gennem vinduet til det inderste objekt med tekst under punktet."""
        node = frame
        text_nodes: list[Ref] = []
        for _ in range(MAX_DEPTH):
            if TEXT in await self.interfaces(node):
                text_nodes.append(node)
            try:
                child = await self.child_at_point(node, x, y, coord)
            except AtspiError:
                break
            if child.is_null or child == node:
                break
            node = child
        for candidate in reversed(text_nodes):  # det inderste først
            try:
                offset = await self.offset_at_point(candidate, x, y, coord)
                if offset < 0:
                    continue
                text = await self.full_text(candidate)
            except AtspiError:
                continue
            if not text.strip():
                continue
            following = await self._following_texts(candidate) if with_following else ()
            return TextHit(_clean(text), min(offset, max(len(text) - 1, 0)), following)
        return None

    # -- den markerede tekst ----------------------------------------------
    async def active_frame(self) -> Ref | None:
        """Det aktive vindue (det, brugeren arbejder i)."""
        for app in await self.applications():
            for frame in await self.frames(app):
                if _has_state(await self._safe_states(frame), STATE_ACTIVE):
                    return frame
        return None

    async def selected_text(self, frame: Ref) -> str:
        """Den markerede tekst i vinduet – også når den går over flere afsnit.

        Kun synlige dele af vinduet gennemsøges, og menuer og værktøjslinjer
        springes over. Søskende spørges samtidig, så det går hurtigt.
        """
        return "\n".join(await self._selections_below(frame, 0))

    async def _selections_below(self, ref: Ref, depth: int) -> list[str]:
        try:
            (role,), states, names = await asyncio.gather(
                self._call(ref, ACCESSIBLE, "GetRoleName"), self.states(ref), self.interfaces(ref)
            )
        except AtspiError:
            return []
        if role in _SKIP_ROLES or not _has_state(states, STATE_SHOWING) or depth > MAX_DEPTH:
            return []
        found: list[str] = []
        if TEXT in names:
            found.extend(await self._own_selections(ref))
        try:
            children = await self.children(ref)
        except AtspiError:
            return found
        below = await asyncio.gather(
            *(self._selections_below(child, depth + 1) for child in children[:MAX_SIBLINGS])
        )
        for texts in below:  # i samme rækkefølge som i dokumentet
            found.extend(texts)
        return found

    async def _own_selections(self, ref: Ref) -> list[str]:
        try:
            (count,) = await self._call(ref, TEXT, "GetNSelections")
            texts = []
            for i in range(count):
                start, end = await self._call(ref, TEXT, "GetSelection", "i", [i])
                if end > start:
                    (text,) = await self._call(ref, TEXT, "GetText", "ii", [start, end])
                    texts.append(_clean(str(text)))
            return texts
        except AtspiError:
            return []

    async def _following_texts(self, ref: Ref) -> tuple[str, ...]:
        """Teksten i de næste afsnit (søskende med tekst), til "læs herfra"."""
        try:
            parent = await self.parent(ref)
            index = await self.index_in_parent(ref)
            siblings = await self.children(parent)
        except AtspiError:
            return ()
        texts: list[str] = []
        for sibling in siblings[index + 1 : index + 1 + MAX_SIBLINGS]:
            try:
                if TEXT in await self.interfaces(sibling):
                    text = _clean(await self.full_text(sibling)).strip()
                    if text:
                        texts.append(text)
            except AtspiError:
                continue
        return tuple(texts)


def _clean(text: str) -> str:
    # U+FFFC står for indlejrede objekter (fx links i Firefox). Det kan ikke læses op.
    return text.replace("￼", " ")
