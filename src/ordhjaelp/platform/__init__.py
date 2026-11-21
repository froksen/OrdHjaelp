"""Vælger den rigtige platformsadapter for det aktuelle styresystem."""

from __future__ import annotations

import sys

from ordhjaelp.platform.base import (
    HotkeyProvider,
    PlatformNotSupported,
    SelectionProvider,
    TextInjector,
)


def get_selection_provider() -> SelectionProvider:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.selection import LinuxSelection

        return LinuxSelection()
    raise PlatformNotSupported(f"Markeret tekst understøttes endnu ikke på {sys.platform}")


def get_hotkey_provider() -> HotkeyProvider:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.hotkeys import PortalHotkeys

        return PortalHotkeys()
    raise PlatformNotSupported(f"Globale genveje understøttes endnu ikke på {sys.platform}")


def get_text_injector() -> TextInjector:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.inject import PortalKeyboard

        return PortalKeyboard()
    raise PlatformNotSupported(f"Indsættelse af tekst understøttes endnu ikke på {sys.platform}")


__all__ = [
    "get_hotkey_provider",
    "get_selection_provider",
    "get_text_injector",
    "PlatformNotSupported",
]
