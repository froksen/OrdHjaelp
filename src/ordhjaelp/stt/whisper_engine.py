"""Tale til tekst med Whisper (faster-whisper, offline)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Kaldenavne til indstillingsfilen. Værdien er et faster-whisper-navn eller et
# Hugging Face-repo i CTranslate2-format. Vi bruger kun færdige modeller, som andre
# vedligeholder – Ordhjælp konverterer eller træner ikke selv modeller.
MODEL_ALIASES: dict[str, str] = {
    "hurtig": "small",
    "turbo": "large-v3-turbo",
    # Danske udgaver – færdigkonverterede af andre, hentes direkte fra Hugging Face
    "dansk-hurtig": "lucasw89/whisper-small-danish-ct2-int8",
    "dansk-turbo": "q-henric/whisper-large-v3-turbo-danish-ct2",
    "dansk-stor": "pluttodk/roest-v3-whisper-1.5b-ct2",  # CoRal røst-v3
}


# Valgmuligheder i indstillingsvinduet: (kaldenavn, beskrivelse)
MODEL_CHOICES: list[tuple[str, str]] = [
    ("dansk-hurtig", "Dansk – hurtig (anbefalet, ca. 250 MB)"),
    ("dansk-turbo", "Dansk – mere præcis, men langsommere (ca. 1,6 GB)"),
    ("dansk-stor", "Dansk – CoRal røst, langsom og uden tegnsætning (ca. 3 GB)"),
    ("hurtig", "Generel – hurtig, men svagere på dansk (ca. 500 MB)"),
    ("turbo", "Generel – præcis (ca. 1,6 GB)"),
]


def resolve_model(name: str) -> str:
    return MODEL_ALIASES.get(name, name)


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
