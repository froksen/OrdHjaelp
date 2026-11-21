"""Læs under musen på Windows: teksten under musen via UI Automation.

Programmet giver afsnittet under musen og tegnets plads i det. Reglerne for ord og
sætning ligger i services/pointer_read.py, så de er ens på Linux og Windows.
"""

from __future__ import annotations

import logging

from ordhjaelp.services.pointer_read import FROM_HERE_MAX_CHARS, extract

log = logging.getLogger(__name__)


class WindowsPointerText:
    def prepare(self) -> None:
        """Intet at gøre: UI Automation er altid slået til på Windows."""

    def text_at_pointer(self, unit: str) -> str | None:
        from ordhjaelp.platform.windows import uia
        from ordhjaelp.platform.windows.typing import mouse_position

        x, y = mouse_position()
        hit = uia.text_at_point(x, y, following=unit == "herfra", max_chars=FROM_HERE_MAX_CHARS)
        if hit is None:
            log.info("Ingen tekst under musen (%d, %d) via UI Automation", x, y)
            return None
        text, offset = hit
        return extract(text, offset, unit) or None
