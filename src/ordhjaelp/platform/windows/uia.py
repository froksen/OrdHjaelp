"""UI Automation: Windows' tilgængeligheds-API (svarer til AT-SPI på Linux).

Bruges til at finde den markerede tekst og teksten under musen, uden at røre
udklipsholderen. Virker i programmer, der understøtter UI Automations
TextPattern, fx Word, Edge, Chrome, Notesblok og Windows Terminal.

Ingen ekstra pakker: COM-objekterne kaldes direkte via deres funktionstabeller
(vtables) med ctypes. Numrene herunder er metodernes plads i tabellerne fra
UIAutomationClient.h.

Hvert opslag kører i sin egen tråd med en tidsgrænse, så et program, der ikke
svarer, aldrig får Ordhjælp til at hænge.
"""

from __future__ import annotations

import contextlib
import ctypes
import functools
import logging
import threading
from collections.abc import Callable, Iterator
from ctypes import wintypes

log = logging.getLogger(__name__)

TIMEOUT = 2.0  # sekunder pr. opslag
MAX_PARENTS = 8  # så mange niveauer op leder vi efter et element med tekst
MAX_CHARS = 100_000

COINIT_MULTITHREADED = 0x0
CLSCTX_INPROC_SERVER = 0x1
UIA_TEXT_PATTERN_ID = 10014

# TextUnit og TextPatternRangeEndpoint
UNIT_WORD = 2
UNIT_PARAGRAPH = 4
ENDPOINT_START = 0
ENDPOINT_END = 1

# -- pladser i funktionstabellerne (IUnknown har 0–2) --------------------------
RELEASE = 2
QUERY_INTERFACE = 0
# IUIAutomation
AUTO_ELEMENT_FROM_POINT = 7
AUTO_GET_FOCUSED_ELEMENT = 8
AUTO_CONTROL_VIEW_WALKER = 14
# IUIAutomationTreeWalker
WALKER_GET_PARENT = 3
# IUIAutomationElement
ELEMENT_GET_CURRENT_PATTERN_AS = 14
ELEMENT_CURRENT_PROCESS_ID = 20
# IUIAutomationTextPattern
TEXT_RANGE_FROM_POINT = 3
TEXT_GET_SELECTION = 5
TEXT_DOCUMENT_RANGE = 7
# IUIAutomationTextRangeArray
ARRAY_LENGTH = 3
ARRAY_GET_ELEMENT = 4
# IUIAutomationTextRange
RANGE_CLONE = 3
RANGE_EXPAND_TO_ENCLOSING_UNIT = 6
RANGE_GET_TEXT = 12
RANGE_MOVE_ENDPOINT_BY_RANGE = 15


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text: str) -> GUID:
        import uuid

        b = uuid.UUID(text).bytes_le
        return cls.from_buffer_copy(b)


CLSID_CUIAUTOMATION = "{FF48DBA4-60EF-4201-AA87-54103EEF594E}"
IID_IUIAUTOMATION = "{30CBE57D-D9D0-452A-AB13-7AC5AC4825EE}"
IID_IUIAUTOMATION_TEXT_PATTERN = "{32EBA289-3583-42C9-9C59-3B6D9A1E9B6A}"


class UiaError(OSError):
    pass


@functools.cache
def _ole32():  # noqa: ANN202
    dll = ctypes.WinDLL("ole32")
    dll.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    dll.CoInitializeEx.restype = ctypes.c_long
    dll.CoUninitialize.restype = None
    guid_p, out_p = ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)
    dll.CoCreateInstance.argtypes = [guid_p, ctypes.c_void_p, wintypes.DWORD, guid_p, out_p]
    dll.CoCreateInstance.restype = ctypes.c_long
    return dll


@functools.cache
def _oleaut32():  # noqa: ANN202
    dll = ctypes.WinDLL("oleaut32")
    dll.SysFreeString.argtypes = [ctypes.c_void_p]
    dll.SysFreeString.restype = None
    dll.SysStringLen.argtypes = [ctypes.c_void_p]
    dll.SysStringLen.restype = wintypes.UINT
    return dll


def _check(hr: int, what: str) -> None:
    if hr < 0:
        raise UiaError(hr & 0xFFFFFFFF, f"{what} fejlede (0x{hr & 0xFFFFFFFF:08X})")


class Com:
    """Et COM-objekt. Frigives med release() eller som context manager."""

    def __init__(self, ptr: int) -> None:
        self.ptr = ptr

    def call(self, index: int, what: str, *args: tuple[object, object]) -> None:
        """Kald metode nr. index. args er par af (ctypes-type, værdi)."""
        argtypes = [t for t, _ in args]
        proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
        vtable = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        _check(proto(vtable[index])(self.ptr, *[v for _, v in args]), what)

    def get_object(self, index: int, what: str, *args: tuple[object, object]) -> Com | None:
        """Kald en metode, der giver et nyt COM-objekt som sidste (ud-)argument."""
        out = ctypes.c_void_p()
        self.call(index, what, *args, (ctypes.POINTER(ctypes.c_void_p), ctypes.byref(out)))
        return Com(out.value) if out.value else None

    def get_int(self, index: int, what: str) -> int:
        out = ctypes.c_int()
        self.call(index, what, (ctypes.POINTER(ctypes.c_int), ctypes.byref(out)))
        return out.value

    def release(self) -> None:
        if self.ptr:
            proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
            vtable = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            proto(vtable[RELEASE])(self.ptr)
            self.ptr = 0

    def __enter__(self) -> Com:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


# -- tekstområder ----------------------------------------------------------------
def range_text(text_range: Com, max_chars: int = MAX_CHARS) -> str:
    bstr = ctypes.c_void_p()
    text_range.call(
        RANGE_GET_TEXT,
        "GetText",
        (ctypes.c_int, max_chars),
        (ctypes.POINTER(ctypes.c_void_p), ctypes.byref(bstr)),
    )
    if not bstr.value:
        return ""
    try:
        return ctypes.wstring_at(bstr.value, _oleaut32().SysStringLen(bstr.value))
    finally:
        _oleaut32().SysFreeString(bstr.value)


def _clone(text_range: Com) -> Com:
    clone = text_range.get_object(RANGE_CLONE, "Clone")
    if clone is None:
        raise UiaError(0, "Clone gav intet")
    return clone


def _expand(text_range: Com, unit: int) -> None:
    text_range.call(RANGE_EXPAND_TO_ENCLOSING_UNIT, "ExpandToEnclosingUnit", (ctypes.c_int, unit))


def _move_endpoint(text_range: Com, endpoint: int, target: Com, target_endpoint: int) -> None:
    text_range.call(
        RANGE_MOVE_ENDPOINT_BY_RANGE,
        "MoveEndpointByRange",
        (ctypes.c_int, endpoint),
        (ctypes.c_void_p, target.ptr),
        (ctypes.c_int, target_endpoint),
    )


# -- selve opslagene -------------------------------------------------------------
@contextlib.contextmanager
def _automation() -> Iterator[Com]:
    """IUIAutomation i den aktuelle tråd (MTA, som Microsoft anbefaler til UI Automation)."""
    ole = _ole32()
    initialized = ole.CoInitializeEx(None, COINIT_MULTITHREADED) >= 0
    try:
        out = ctypes.c_void_p()
        clsid, iid = GUID.parse(CLSID_CUIAUTOMATION), GUID.parse(IID_IUIAUTOMATION)
        _check(
            ole.CoCreateInstance(
                ctypes.byref(clsid),
                None,
                CLSCTX_INPROC_SERVER,
                ctypes.byref(iid),
                ctypes.byref(out),
            ),  # fmt: skip
            "CoCreateInstance(CUIAutomation)",
        )
        with Com(out.value) as automation:
            yield automation
    finally:
        if initialized:
            ole.CoUninitialize()


def _text_pattern(automation: Com, element: Com) -> Com | None:
    """TextPattern på elementet eller et af dets forældre (fx dokumentet om en tekstbid)."""
    iid = GUID.parse(IID_IUIAUTOMATION_TEXT_PATTERN)
    walker = automation.get_object(AUTO_CONTROL_VIEW_WALKER, "ControlViewWalker")
    if walker is None:
        return None
    with walker:
        current = Com(element.ptr)
        owned = False
        try:
            for _ in range(MAX_PARENTS):
                try:
                    pattern = current.get_object(
                        ELEMENT_GET_CURRENT_PATTERN_AS,
                        "GetCurrentPatternAs",
                        (ctypes.c_int, UIA_TEXT_PATTERN_ID),
                        (ctypes.POINTER(GUID), ctypes.byref(iid)),
                    )
                except UiaError:
                    pattern = None
                if pattern is not None:
                    return pattern
                try:
                    parent = walker.get_object(
                        WALKER_GET_PARENT, "GetParentElement", (ctypes.c_void_p, current.ptr)
                    )
                except UiaError:
                    parent = None
                if owned:
                    current.release()
                if parent is None:
                    return None
                current, owned = parent, True
            return None
        finally:
            if owned:
                current.release()


def _selection(max_chars: int) -> str | None:
    with _automation() as automation:
        focused = automation.get_object(AUTO_GET_FOCUSED_ELEMENT, "GetFocusedElement")
        if focused is None:
            return None
        with focused:
            pattern = _text_pattern(automation, focused)
        if pattern is None:
            return None  # programmet understøtter ikke tekst via UI Automation
        with pattern:
            ranges = pattern.get_object(TEXT_GET_SELECTION, "GetSelection")
            if ranges is None:
                return ""
            with ranges:
                texts = []
                for i in range(ranges.get_int(ARRAY_LENGTH, "Length")):
                    item = ranges.get_object(ARRAY_GET_ELEMENT, "GetElement", (ctypes.c_int, i))
                    if item is not None:
                        with item:
                            texts.append(range_text(item, max_chars))
                return "\n".join(t for t in texts if t)


def _at_point(x: int, y: int, following: bool, max_chars: int) -> tuple[str, int] | None:
    """Afsnittet under punktet og tegnets plads i det. Med following: resten af teksten med."""
    point = wintypes.POINT(x, y)
    with _automation() as automation:
        element = automation.get_object(
            AUTO_ELEMENT_FROM_POINT, "ElementFromPoint", (wintypes.POINT, point)
        )
        if element is None:
            return None
        with element:
            pattern = _text_pattern(automation, element)
        if pattern is None:
            return None
        with pattern:
            at = pattern.get_object(
                TEXT_RANGE_FROM_POINT, "RangeFromPoint", (wintypes.POINT, point)
            )
            if at is None:
                return None
            with at, _clone(at) as paragraph:
                _expand(paragraph, UNIT_PARAGRAPH)
                with _clone(paragraph) as before:
                    _move_endpoint(before, ENDPOINT_END, at, ENDPOINT_START)
                    offset = len(range_text(before, max_chars))
                if following:
                    document = pattern.get_object(TEXT_DOCUMENT_RANGE, "DocumentRange")
                    if document is not None:
                        with document:
                            _move_endpoint(paragraph, ENDPOINT_END, document, ENDPOINT_END)
                return range_text(paragraph, offset + max_chars), offset


def run_with_timeout[T](fn: Callable[[], T], timeout: float = TIMEOUT) -> T | None:
    """Kør et opslag i en egen tråd. None, hvis det fejler eller tager for lang tid."""
    result: list[T] = []

    def work() -> None:
        try:
            result.append(fn())
        except Exception as exc:  # noqa: BLE001 - programmer svarer på mange mærkelige måder
            log.info("UI Automation: %s", exc)

    thread = threading.Thread(target=work, daemon=True, name="uia")
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        log.info("UI Automation svarede ikke inden for %.1f s", timeout)
        return None
    return result[0] if result else None


def selected_text(max_chars: int = MAX_CHARS) -> str | None:
    """Den markerede tekst i det aktive program.

    None: programmet understøtter ikke UI Automation (prøv Ctrl+C i stedet).
    "": programmet understøtter det, men intet er markeret.
    """
    return run_with_timeout(lambda: _selection(max_chars))


def text_at_point(
    x: int, y: int, following: bool = False, max_chars: int = MAX_CHARS
) -> tuple[str, int] | None:
    """(afsnittets tekst, tegnets plads i den) under punktet på skærmen, eller None."""
    return run_with_timeout(lambda: _at_point(x, y, following, max_chars))
