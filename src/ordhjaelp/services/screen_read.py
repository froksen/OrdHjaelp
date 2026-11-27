"""Tjenesten 'læs fra skærmen' – uafhængig af styresystem og brugerflade.

Brugerfladen tager sig af at lade eleven vælge et udsnit; denne tjeneste tager
skærmbilledet og laver udsnittet om til tekst, der læses op.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

from ordhjaelp.platform.base import ScreenCapture

log = logging.getLogger(__name__)

MSG_NO_TEXT = "Jeg kunne ikke finde noget tekst. Prøv at markere et større område."
MSG_NO_OCR = "Tekstgenkendelse er ikke installeret på computeren."
MSG_ERROR = "Jeg kunne ikke læse skærmen. Prøv igen."


class OcrUnavailable(RuntimeError):
    """Tekstgenkendelse (eller sprogpakken) er ikke installeret."""


class OCR(Protocol):
    def recognize(self, png: bytes) -> str: ...


class ScreenReadService:
    def __init__(
        self,
        capture: ScreenCapture,
        ocr: OCR,
        say: Callable[[str], object],
        stop_reading: Callable[[], None] | None = None,
    ) -> None:
        self._capture = capture
        self._ocr = ocr
        self._say = say
        self._stop_reading = stop_reading

    def take_screenshot(self) -> bytes | None:
        """Hele skærmen som PNG, eller None ved fejl (eleven får en talt besked)."""
        if self._stop_reading:
            self._stop_reading()
        try:
            return self._capture.capture()
        except Exception:
            log.exception("Skærmbillede fejlede")
            self._say(MSG_ERROR)
            return None

    def read_image(self, png: bytes) -> str:
        """Genkend tekst i et udsnit og læs den op. Returnerer den fundne tekst."""
        try:
            text = self._ocr.recognize(png).strip()
        except OcrUnavailable as exc:
            log.warning("%s", exc)
            self._say(MSG_NO_OCR)
            return ""
        except Exception:
            log.exception("Tekstgenkendelse fejlede")
            self._say(MSG_ERROR)
            return ""
        # Selve teksten kun ved fejlfinding (-v): loggen må ikke gemme elevens tekst
        log.info("Fundet %d tegn på skærmen", len(text))
        log.debug("Fundet på skærmen: %r", text[:200])
        self._say(text or MSG_NO_TEXT)
        return text
