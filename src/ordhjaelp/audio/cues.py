"""Korte lydsignaler, så eleven kan høre, at optagelsen starter og stopper."""

from __future__ import annotations

import logging

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

_RATE = 44100


def _tone(freqs: list[float], length: float = 0.09, volume: float = 0.25) -> np.ndarray:
    parts = []
    for f in freqs:
        t = np.arange(int(_RATE * length)) / _RATE
        envelope = np.minimum(1, np.minimum(t, length - t) / 0.01)  # blød start/slut
        parts.append(np.sin(2 * np.pi * f * t) * envelope * volume)
    return np.concatenate(parts).astype(np.float32)


class Cues:
    def __init__(self) -> None:
        self._start = _tone([660, 990])  # stigende: "nu lytter jeg"
        self._stop = _tone([990, 660])  # faldende: "færdig"

    def start(self) -> None:
        self._play(self._start)

    def stop(self) -> None:
        self._play(self._stop)

    @staticmethod
    def _play(sound: np.ndarray) -> None:
        try:
            sd.play(sound, _RATE, blocking=True)
        except Exception as exc:  # noqa: BLE001 - lyd er ikke kritisk
            log.debug("Kunne ikke afspille lydsignal: %s", exc)
