"""Afspilning af lyd, der kan stoppes midt i en sætning."""

from __future__ import annotations

import threading
from collections.abc import Iterable

import numpy as np
import sounddevice as sd

from ordhjaelp.tts.piper_engine import SpeechChunk

_BLOCK = 1024  # frames pr. skrivning (~45 ms ved 22050 Hz)


class Player:
    def play(self, chunks: Iterable[SpeechChunk], stop: threading.Event) -> None:
        """Afspil sætninger efterhånden som de bliver klar. Returnerer når færdig/stoppet."""
        stream: sd.OutputStream | None = None
        try:
            for chunk in chunks:
                if stop.is_set():
                    return
                if stream is None:
                    stream = sd.OutputStream(
                        samplerate=chunk.sample_rate, channels=1, dtype="int16"
                    )
                    stream.start()
                audio = np.ascontiguousarray(chunk.audio, dtype=np.int16).reshape(-1, 1)
                for start in range(0, len(audio), _BLOCK):
                    if stop.is_set():
                        stream.abort()
                        return
                    stream.write(audio[start : start + _BLOCK])
                # kort pause mellem sætninger
                stream.write(np.zeros((int(chunk.sample_rate * 0.15), 1), dtype=np.int16))
        finally:
            if stream is not None:
                if not stop.is_set():
                    stream.stop()  # lad bufferen spille færdig
                stream.close()
