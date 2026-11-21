"""Fælles for alle styresystemer: er en markering ny, eller er den allerede læst op?"""

from __future__ import annotations


class FreshnessTracker:
    """Afgør om en markering er ny eller allerede læst op.

    serial er et tal, der stiger hver gang markeringen ændrer sig (eller None,
    hvis vi ikke kan overvåge ændringer – så sammenlignes kun teksten).
    """

    def __init__(self) -> None:
        self._last: tuple[str, int | None] | None = None

    def fresh(self, text: str | None, serial: int | None) -> str | None:
        if not text:
            return None
        if self._last is not None:
            last_text, last_serial = self._last
            if text == last_text and serial == last_serial:
                return None  # samme markering som sidst – allerede læst op
        self._last = (text, serial)
        return text
