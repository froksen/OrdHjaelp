"""Vælger den rigtige platformsadapter for det aktuelle styresystem."""

from __future__ import annotations

import sys

from ordhjaelp.platform.base import (
    Autostart,
    HotkeyProvider,
    PlatformNotSupported,
    ScreenCapture,
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


def get_screen_capture() -> ScreenCapture:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.screenshot import PortalScreenshot

        return PortalScreenshot()
    raise PlatformNotSupported(f"Skærmbilleder understøttes endnu ikke på {sys.platform}")


def get_autostart() -> Autostart:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.install import LinuxAutostart

        return LinuxAutostart()
    raise PlatformNotSupported(f"Autostart understøttes endnu ikke på {sys.platform}")


__all__ = [
    "get_autostart",
    "get_hotkey_provider",
    "get_screen_capture",
    "get_selection_provider",
    "get_text_injector",
    "PlatformNotSupported",
]
