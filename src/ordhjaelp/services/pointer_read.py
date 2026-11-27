"""Læs under musen: læs ordet, sætningen eller resten af teksten, hvor musen står.

Uafhængig af styresystem. Platformen finder teksten og positionen under musen
(på Linux via tilgængeligheds-API'en AT-SPI). Her ligger reglerne for, hvad et
ord og en sætning er, så de er ens i alle programmer.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from ordhjaelp.platform.base import PointerText

log = logging.getLogger(__name__)

UNITS = ("ord", "saetning", "herfra")
MSG_NOTHING = "Jeg kan ikke finde noget tekst under musen."
# "Læs herfra" stopper efter så mange tegn, så et helt langt dokument ikke låser oplæsningen
FROM_HERE_MAX_CHARS = 20000

_WORD_CHAR = re.compile(r"[\w'’-]")
# Sætningen slutter ved . ! ? efterfulgt af mellemrum (eller tekstens slutning)
_SENTENCE_END = re.compile(r"[.!?…]+[\"'”»)]*(?=\s|$)")


def _in_range(text: str, offset: int) -> bool:
    return 0 <= offset < len(text)


def _word_start(text: str, offset: int) -> int:
    start = offset
    while start > 0 and _WORD_CHAR.match(text[start - 1]):
        start -= 1
    return start


def word_at(text: str, offset: int) -> str:
    """Ordet, som tegnet på offset er en del af (tom streng mellem ord)."""
    if not _in_range(text, offset) or not _WORD_CHAR.match(text[offset]):
        return ""
    start = _word_start(text, offset)
    end = offset
    while end < len(text) and _WORD_CHAR.match(text[end]):
        end += 1
    return text[start:end].strip("'’-")


def sentence_at(text: str, offset: int) -> str:
    """Sætningen omkring offset, med tegnet i slutningen."""
    if not _in_range(text, offset):
        return ""
    start = 0
    for match in _SENTENCE_END.finditer(text):
        if match.end() <= offset:
            start = match.end()
            continue
        return text[start : match.end()].strip()
    return text[start:].strip()


def from_here(text: str, offset: int) -> str:
    """Teksten fra begyndelsen af ordet ved offset og resten af vejen."""
    if not _in_range(text, offset):
        return ""
    return text[_word_start(text, offset) :].strip()


def extract(text: str, offset: int, unit: str) -> str:
    if unit == "ord":
        return word_at(text, offset)
    if unit == "saetning":
        return sentence_at(text, offset)
    if unit == "herfra":
        return from_here(text, offset)[:FROM_HERE_MAX_CHARS]
    raise ValueError(f"ukendt enhed: {unit}")


class PointerReadService:
    def __init__(self, provider: PointerText, say: Callable[[str], object]) -> None:
        self._provider = provider
        self._say = say

    def read(self, unit: str) -> bool:
        """Læs ord, sætning eller herfra under musen op. Returnerer True, hvis der var tekst."""
        if unit not in UNITS:
            raise ValueError(f"ukendt enhed: {unit}")
        try:
            text = self._provider.text_at_pointer(unit)
        except Exception:
            log.exception("Kunne ikke finde teksten under musen")
            text = None
        if not text or not text.strip():
            self._say(MSG_NOTHING)
            return False
        # Selve teksten kun ved fejlfinding (-v): loggen må ikke gemme elevens tekst
        log.info("Under musen (%s): %d tegn", unit, len(text))
        log.debug("Under musen (%s): %r", unit, text[:200])
        self._say(text)
        return True
