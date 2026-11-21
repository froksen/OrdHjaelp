"""Læs ved markering: læs automatisk op, når eleven markerer tekst med musen.

Dobbeltklik markerer et ord, trippelklik en linje eller et afsnit. Så snart
markeringen har ligget stille et øjeblik, læses den op. Uafhængig af styresystem:
platformen melder blot, at markeringen har ændret sig.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

# Mens musen trækkes, ændrer markeringen sig mange gange. Vent til den ligger stille.
DEFAULT_DELAY = 0.6


class SelectionAutoReader:
    def __init__(
        self,
        read: Callable[[], bool],
        delay: float = DEFAULT_DELAY,
        enabled: bool = False,
    ) -> None:
        """:param read: læser den nye markering op (fx ReadAloudService.read_new_selection)."""
        self._read = read
        self._delay = delay
        self._enabled = enabled
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self._cancel()

    def selection_changed(self) -> None:
        """Kaldes af platformen, hver gang markeringen ændrer sig (fra en vilkårlig tråd)."""
        if not self._enabled:
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._delay, self._fire)
            self._timer.daemon = True
            self._timer.name = "read-on-select"
            self._timer.start()

    def wait(self, timeout: float = 2) -> None:
        """Vent på en igangværende forsinkelse (bruges i tests)."""
        timer = self._timer
        if timer is not None:
            timer.join(timeout)

    def _cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _fire(self) -> None:
        if not self._enabled:
            return
        try:
            self._read()
        except Exception:
            log.exception("Fejl under læs ved markering")
