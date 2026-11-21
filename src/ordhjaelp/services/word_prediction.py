"""Tjenesten 'ordforslag' – uafhængig af styresystem.

Ordlisten indlæses i baggrunden (første gang bygges den; det tager et par
sekunder). Ord, eleven bruger, huskes lokalt på computeren, så de foreslås
oftere – og nye ord (fx navne) kommer med i forslagene.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from ordhjaelp.ordmotor.lexicon import load_entries
from ordhjaelp.ordmotor.predictor import Predictor

log = logging.getLogger(__name__)

SAVE_EVERY = 10  # gem egne ord efter så mange nye


class WordPredictionService:
    def __init__(self, lexicon_cache: Path, learned_path: Path, count: int = 5) -> None:
        self._lexicon_cache = lexicon_cache
        self._learned_path = learned_path
        self._count = count
        self._predictor: Predictor | None = None
        self._lock = threading.Lock()
        self._unsaved = 0

    def load_in_background(self) -> None:
        threading.Thread(target=self._load, daemon=True, name="ordliste").start()

    def _load(self) -> None:
        try:
            entries = load_entries(self._lexicon_cache)
            predictor = Predictor(entries, self._read_learned())
        except Exception:
            log.exception("Kunne ikke indlæse ordlisten")
            return
        with self._lock:
            self._predictor = predictor
        log.info("Ordforslag klar")

    @property
    def ready(self) -> bool:
        return self._predictor is not None

    def suggest(self, typed: str) -> list[str]:
        predictor = self._predictor
        if predictor is None or not typed:
            return []
        return [s.word for s in predictor.suggest(typed, n=self._count)]

    def learn(self, word: str) -> None:
        predictor = self._predictor
        if predictor is None:
            return
        with self._lock:
            predictor.learn(word)
            self._unsaved += 1
            if self._unsaved >= SAVE_EVERY:
                self._save_locked()

    def save(self) -> None:
        with self._lock:
            if self._unsaved:
                self._save_locked()

    def _save_locked(self) -> None:
        if self._predictor is None:
            return
        try:
            self._learned_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._learned_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._predictor.learned, ensure_ascii=False, indent=0), "utf-8"
            )
            tmp.replace(self._learned_path)
            self._unsaved = 0
        except OSError:
            log.exception("Kunne ikke gemme egne ord")

    def _read_learned(self) -> dict[str, int]:
        try:
            data = json.loads(self._learned_path.read_text("utf-8"))
            return {str(k): int(v) for k, v in data.items()}
        except (OSError, ValueError, AttributeError):
            return {}
