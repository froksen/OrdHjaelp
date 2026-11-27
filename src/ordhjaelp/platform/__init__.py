"""Vælger den rigtige platformsadapter for det aktuelle styresystem."""

from __future__ import annotations

import logging
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


def is_store_app() -> bool:
    """Kører Ordhjælp fra en MSIX-pakke (Microsoft Store)? Altid nej uden for Windows."""
    if sys.platform != "win32":
        return False
    from ordhjaelp.platform.windows.store import is_packaged

    return is_packaged()


def get_autostart() -> Autostart:
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.install import LinuxAutostart

        return LinuxAutostart()
    if sys.platform == "win32":
        if is_store_app():  # MSIX-pakken: start ved login er en StartupTask i manifestet
            from ordhjaelp.platform.windows.store import StoreAutostart

            return StoreAutostart()
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


def open_tray_icon_settings() -> bool:
    """Åbn Windows' indstillinger for ikonerne ved uret. False, hvor det ikke findes."""
    if sys.platform == "win32":
        import os

        try:
            os.startfile("ms-settings:taskbar")  # type: ignore[attr-defined]  # noqa: S606
        except OSError:
            return False
        return True
    return False


def pin_window_in_corner(caption: str, margin: int) -> bool:
    """Læg vinduet nederst til højre over opgavelinjen, altid øverst og uden for opgavelinjen.

    Bruges på Wayland, hvor Qt's move(), WindowStaysOnTopHint og Tool ikke virker.
    Virker på KDE Plasma (KWin).
    Returnerer False, hvor det ikke kan lade sig gøre. Venter på
    D-Bus, så kald den ikke fra Qt's hovedtråd.
    """
    if sys.platform.startswith("linux"):
        import asyncio

        from ordhjaelp.platform.linux.kwin_place import pin_in_corner

        try:
            return asyncio.run(pin_in_corner(caption, margin))
        except Exception as exc:  # noqa: BLE001 - placeringen er en hjælp, ikke vigtig
            logging.getLogger(__name__).debug("KWin kunne ikke flytte %s: %s", caption, exc)
            return False
    return False


__all__ = [
    "pin_window_in_corner",
    "open_tray_icon_settings",
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
