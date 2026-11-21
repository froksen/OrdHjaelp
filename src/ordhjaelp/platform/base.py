"""Interfaces mellem kernen og styresystemet.

Kernen må kun bruge disse Protocol-klasser. Alt OS-specifikt ligger i
platform/linux, platform/windows og platform/macos.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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

    def on_change(self, callback: Callable[[], None]) -> bool:
        """Kald callback (fra en baggrundstråd), hver gang markeringen ændrer sig.

        Returnerer False, hvis styresystemet ikke kan melde ændringer.
        """
        ...


class PointerText(Protocol):
    """Teksten under musen (læs under musen)."""

    def prepare(self) -> None:
        """Gør klar, fx ved at bede programmerne om at slå tilgængelighed til."""
        ...

    def text_at_pointer(self, unit: str) -> str | None:
        """Ordet ("ord"), sætningen ("saetning") eller resten ("herfra") under musen."""
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


class TrayExtension(Protocol):
    """En tilføjelse til skrivebordet, som ikonerne ved uret kræver (fx på GNOME)."""

    name: str  # tilføjelsens navn, som brugeren ser det
    install_command: str  # kommando, der installerer den

    def state(self) -> str:
        """Tilstanden: mangler, slået fra eller slået til."""
        ...

    def enable(self) -> bool:
        """Slå tilføjelsen til. False, hvis det ikke lykkedes."""
        ...

    def wait_until_ready(self, timeout: float) -> bool:
        """Vent på, at ikonerne kan vises. False, hvis det ikke sker inden for tiden."""
        ...


class PlatformNotSupported(RuntimeError):
    pass


@dataclass(frozen=True)
class SetupCheck:
    """Ét punkt i et opsætningstjek, fx "IBus er valgt som virtuelt tastatur"."""

    label: str
    ok: bool
    fix: str = ""  # hvad brugeren skal gøre, hvis punktet ikke er i orden


class TypingSetup(Protocol):
    """Opsætningen af styresystemet, som ordforslag og læs mens du skriver kræver."""

    intro: str  # første afsnit i vejledningen
    settings_button: str | None  # teksten på knappen til systemets indstillinger (None = ingen)

    def checks(self) -> list[SetupCheck]:
        """Tjek opsætningen nu. Hurtigt nok til at kalde fra brugerfladen."""
        ...

    def guide(self) -> list[str]:
        """Trinene i vejledningen, i den rækkefølge de skal gøres."""
        ...

    def open_settings(self) -> bool:
        """Åbn systemets indstillinger på det rette sted. False, hvis det ikke kan lade sig gøre."""
        ...
