"""En stum stemme, når stemmen ikke er hentet (kun diktering med beskeder på skærmen).

Så kan resten af Ordhjælp bruge oplæsningen, som den plejer, uden at noget læses op.
"""

from __future__ import annotations

from collections.abc import Iterator

from ordhjaelp.tts.piper_engine import SpeechChunk


class SilentTTS:
    def __init__(self, speed: float = 1.0) -> None:
        self.speed = speed

    def synthesize(self, text: str) -> Iterator[SpeechChunk]:  # noqa: ARG002
        return iter(())
