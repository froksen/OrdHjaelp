"""Sammenlign talegenkendelsesmodeller med en rigtig optagelse.

Brug: ordhjaelp sammenlign-modeller [--fil optagelse.wav] [MODEL ...]
"""

from __future__ import annotations

import time
import wave
from pathlib import Path

import numpy as np

from ordhjaelp.audio.recorder import SAMPLE_RATE, Recorder
from ordhjaelp.stt.whisper_engine import WhisperEngine

DEFAULT_MODELS = ["hurtig", "dansk-hurtig", "turbo", "dansk-turbo", "dansk-stor"]


def record_interactively() -> np.ndarray:
    recorder = Recorder()
    input("Tryk Enter og sig en sætning … ")
    recorder.start()
    input("🎤 Optager – tryk Enter, når du er færdig ")
    return recorder.stop()


def save_wav(audio: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 1:
            raise ValueError("Filen skal være 16 kHz mono (brug en fil gemt af dette værktøj)")
        data = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768


def compare(audio: np.ndarray, models: list[str], download_dir: Path) -> None:
    print(f"\nLyd: {len(audio) / SAMPLE_RATE:.1f} sekunder\n")
    for name in models:
        engine = WhisperEngine(name, download_dir)
        try:
            t0 = time.perf_counter()
            engine.preload()
            loaded = time.perf_counter() - t0
            t0 = time.perf_counter()
            text = engine.transcribe(audio)
            took = time.perf_counter() - t0
        except Exception as exc:  # noqa: BLE001
            print(f"{name:<12} FEJL: {exc}\n")
            continue
        print(f"{name:<12} {took:5.1f} s  (indlæsning {loaded:.1f} s)\n             {text}\n")
