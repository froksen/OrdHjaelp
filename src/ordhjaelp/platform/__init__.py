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
    TrayExtension,
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


def get_tray_extension() -> TrayExtension | None:
    """Den tilføjelse, skrivebordet kræver for at vise ikoner ved uret (None = ingen)."""
    if sys.platform.startswith("linux"):
        from ordhjaelp.platform.linux.gnome import AppIndicatorExtension, is_gnome

        return AppIndicatorExtension() if is_gnome() else None
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


__all__ = [
    "open_tray_icon_settings",
    "get_input_method",
    "get_typing_setup",
    "get_tray_extension",
    "get_autostart",
    "get_hotkey_provider",
    "get_pointer_text",
    "get_screen_capture",
    "get_selection_provider",
    "get_text_injector",
    "PlatformNotSupported",
]
