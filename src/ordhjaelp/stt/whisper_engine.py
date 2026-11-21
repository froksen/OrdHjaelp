"""Tale til tekst med Whisper (faster-whisper, offline)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


def resolve_model(name: str) -> str:
    """Kaldenavn fra indstillingerne (fx "dansk-hurtig") → det, faster-whisper skal hente.

    Ukendte navne bruges som de er (faster-whisper-navn eller Hugging Face-repo).
    """
    from ordhjaelp.models.catalog import Kind, get

    model = get(name)
    return model.source if model is not None and model.kind is Kind.SPEECH else name


class WhisperEngine:
    def __init__(self, model: str, download_dir: Path, language: str = "da") -> None:
        self._model_name = model
        self._download_dir = download_dir
        self._language = language
        self._model = None
        self._lock = threading.Lock()

    def preload(self) -> None:
        """Indlæs (og evt. hent) modellen, så første diktering går hurtigt."""
        self._get_model()

    def _get_model(self):  # noqa: ANN202
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                log.info("Indlæser talegenkendelse (%s) …", self._model_name)
                self._download_dir.mkdir(parents=True, exist_ok=True)
                self._model = WhisperModel(
                    resolve_model(self._model_name),
                    device="cpu",
                    compute_type="int8",
                    download_root=str(self._download_dir),
                )
                log.info("Talegenkendelse klar")
            return self._model

    def transcribe(self, audio: np.ndarray) -> str:
        model = self._get_model()
        segments, _ = model.transcribe(
            audio,
            language=self._language,
            beam_size=1,
            vad_filter=True,  # fjern stilhed – mindre risiko for "hallucinationer"
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
