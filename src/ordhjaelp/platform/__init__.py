"""Vælger den rigtige platformsadapter for det aktuelle styresystem."""

from __future__ import annotations

import sys

from ordhjaelp.platform.base import (
    Autostart,
    HotkeyProvider,
    InputMethod,
    PlatformNotSupported,
    PointerText,
    ScreenCapture,
    SelectionProvider,
    TextInjector,
    TypingSetup,
)


def get_selection_provider() -> SelectionProvider:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.selection import LinuxSelection

        return LinuxSelection()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.selection import WindowsSelection

        return WindowsSelection()
    raise PlatformNotSupported(f"Markeret tekst understøttes endnu ikke på {sys.platform}")


def get_hotkey_provider() -> HotkeyProvider:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.hotkeys import PortalHotkeys

        return PortalHotkeys()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.hotkeys import WindowsHotkeys

        return WindowsHotkeys()
    raise PlatformNotSupported(f"Globale genveje understøttes endnu ikke på {sys.platform}")


def get_text_injector() -> TextInjector:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.inject import PortalKeyboard

        return PortalKeyboard()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.inject import WindowsKeyboard

        return WindowsKeyboard()
    raise PlatformNotSupported(f"Indsættelse af tekst understøttes endnu ikke på {sys.platform}")


def get_screen_capture() -> ScreenCapture:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.screenshot import PortalScreenshot

        return PortalScreenshot()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.screenshot import WindowsScreenshot

        return WindowsScreenshot()
    raise PlatformNotSupported(f"Skærmbilleder understøttes endnu ikke på {sys.platform}")


def get_pointer_text() -> PointerText:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.pointer import LinuxPointerText

        return LinuxPointerText()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.pointer import WindowsPointerText

        return WindowsPointerText()
    raise PlatformNotSupported(f"Læs under musen understøttes endnu ikke på {sys.platform}")


def get_autostart() -> Autostart:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.install import LinuxAutostart

        return LinuxAutostart()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.install import WindowsAutostart

        return WindowsAutostart()
    raise PlatformNotSupported(f"Autostart understøttes endnu ikke på {sys.platform}")


def get_input_method() -> InputMethod:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.ibus import IBusInputMethod

        return IBusInputMethod()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.typing import WindowsInputMethod

        return WindowsInputMethod()
    raise PlatformNotSupported(f"Ordforslag understøttes endnu ikke på {sys.platform}")


def get_typing_setup() -> TypingSetup | None:
    """Opsætningstjek til ordforslag og læs mens du skriver (None, hvor det ikke findes)."""
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.ibus import IBusSetup

        return IBusSetup()
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.typing import WindowsTypingSetup

        return WindowsTypingSetup()
    return None


def set_tray_icons_always_visible(visible: bool) -> bool:
    """Vis ikonerne ved uret i stedet for gemt under ^ (kun Windows 11). True = ændret."""
    if sys.platform == "win32":
        from ordhjaelp.platform.windows.tray_icons import set_promoted

        try:
            return set_promoted(visible) > 0
        except OSError:
            return False
    return False


__all__ = [
    "set_tray_icons_always_visible",
    "get_input_method",
    "get_typing_setup",
    "get_autostart",
    "get_hotkey_provider",
    "get_pointer_text",
    "get_screen_capture",
    "get_selection_provider",
    "get_text_injector",
    "PlatformNotSupported",
]
