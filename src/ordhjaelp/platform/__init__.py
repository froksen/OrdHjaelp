"""Vælger den rigtige platformsadapter for det aktuelle styresystem."""

from __future__ import annotations

import sys

from ordhjaelp.platform.base import HotkeyProvider, PlatformNotSupported, SelectionProvider


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


__all__ = ["get_hotkey_provider", "get_selection_provider", "PlatformNotSupported"]
