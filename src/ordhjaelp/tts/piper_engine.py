"""Oplæsning med Piper (offline, neural dansk stemme)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class SpeechChunk:
    """Lyd for én sætning."""

    audio: np.ndarray  # int16, mono
    sample_rate: int


def ensure_voice(voice: str, directory: Path) -> Path:
    """Hent stemmen fra Hugging Face, hvis den ikke allerede ligger lokalt."""
    model = directory / f"{voice}.onnx"
    if not model.exists() or not (directory / f"{voice}.onnx.json").exists():
        from piper.download_voices import download_voice

        directory.mkdir(parents=True, exist_ok=True)
        log.info("Henter stemmen %s til %s ...", voice, directory)
        download_voice(voice, directory)
    return model


class PiperEngine:
    def __init__(self, model_path: Path, speed: float = 1.0) -> None:
        from piper import PiperVoice, SynthesisConfig

        self._voice = PiperVoice.load(model_path)
        self._make_config = SynthesisConfig
        self.speed = speed

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        """Taletempo – kan ændres, mens programmet kører."""
        if value <= 0:
            raise ValueError("tempo skal være større end 0")
        self._speed = value
        # Piper: length_scale > 1 er langsommere. Vores "tempo" er det omvendte.
        self._config = self._make_config(length_scale=1.0 / value)

    @property
    def sample_rate(self) -> int:
        return self._voice.config.sample_rate

    def synthesize(self, text: str) -> Iterator[SpeechChunk]:
        """Giv lyd sætning for sætning, så oplæsningen kan starte med det samme."""
        for chunk in self._voice.synthesize(text, syn_config=self._config):
            yield SpeechChunk(
                audio=chunk.audio_int16_array,
                sample_rate=chunk.sample_rate,
            )
