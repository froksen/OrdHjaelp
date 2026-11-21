"""Interfaces mellem kernen og styresystemet.

Kernen må kun bruge disse Protocol-klasser. Alt OS-specifikt ligger i
platform/linux, platform/windows og platform/macos.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class SelectionProvider(Protocol):
    def selected_text(self) -> str | None:
        """Returnér den tekst, brugeren har markeret, eller None.

        En gammel markering, som allerede er læst op og ikke er markeret igen
        siden, skal give None – ellers "husker" programmet fjernede markeringer.
        """
        ...

    def clipboard_text(self) -> str | None:
        """Returnér teksten i udklipsholderen, eller None."""
        ...


class HotkeyProvider(Protocol):
    def start(self, bindings: dict[str, str], on_activated: Callable[[str], None]) -> None:
        """Registrér globale genveje.

        :param bindings: handling -> ønsket genvej, fx {"laes": "CTRL+ALT+L"}
        :param on_activated: kaldes med handlingens navn, når genvejen trykkes.
        """
        ...

    def stop(self) -> None: ...


class TextInjector(Protocol):
    def insert(self, text: str) -> None:
        """Skriv tekst ind, hvor markøren står i det aktive program."""
        ...


class ScreenCapture(Protocol):
    def capture(self) -> bytes:
        """Tag et billede af hele skærmen og returnér det som PNG."""
        ...


class InputMethod(Protocol):
    """Indtastningsmetode, der viser ordforslag i alle programmer."""

    def start(self) -> bool:
        """Start den. Returnerer False, hvis systemet ikke er sat op til det."""
        ...

    def stop(self) -> None: ...


class Autostart(Protocol):
    def is_enabled(self) -> bool: ...
    def set_enabled(self, enabled: bool) -> None: ...


class PlatformNotSupported(RuntimeError):
    pass
