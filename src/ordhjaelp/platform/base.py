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


class PlatformNotSupported(RuntimeError):
    pass
