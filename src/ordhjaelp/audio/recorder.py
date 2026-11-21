"""Optagelse fra mikrofonen (16 kHz mono, som Whisper vil have det)."""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
MAX_SECONDS = 120  # sikkerhed: stop af sig selv efter 2 minutter


class Recorder:
    def __init__(self) -> None:
        self._stream: sd.InputStream | None = None
        self._blocks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self.on_limit_reached: Callable[[], None] | None = None

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._blocks = []
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=self._callback
            )
            self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop og returnér lyden som float32-array i [-1, 1]."""
        with self._lock:
            stream, self._stream = self._stream, None
            if stream is not None:
                stream.stop()
                stream.close()
            if not self._blocks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._blocks).reshape(-1)
            self._blocks = []
            return audio

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:  # noqa: ANN001
        self._blocks.append(indata.copy())
        if sum(len(b) for b in self._blocks) >= MAX_SECONDS * SAMPLE_RATE and self.on_limit_reached:
            cb, self.on_limit_reached = self.on_limit_reached, None
            threading.Thread(target=cb, daemon=True).start()
