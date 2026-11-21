"""Tjenesten 'læs op' – uafhængig af styresystem."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from typing import Protocol

from ordhjaelp.platform.base import SelectionProvider
from ordhjaelp.textutil import normalize_for_speech
from ordhjaelp.tts.piper_engine import SpeechChunk

log = logging.getLogger(__name__)


class Synthesizer(Protocol):
    def synthesize(self, text: str) -> Iterable[SpeechChunk]: ...


class AudioPlayer(Protocol):
    def play(self, chunks: Iterable[SpeechChunk], stop: threading.Event) -> None: ...


class ReadAloudService:
    def __init__(
        self,
        tts: Synthesizer,
        player: AudioPlayer,
        selection: SelectionProvider,
        use_clipboard_fallback: bool = True,
    ) -> None:
        self._tts = tts
        self._player = player
        self._selection = selection
        self._use_clipboard = use_clipboard_fallback
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

    @property
    def speaking(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def say(self, text: str, on_done: Callable[[], None] | None = None) -> bool:
        """Læs tekst op i baggrunden. Afbryder evt. igangværende oplæsning."""
        text = normalize_for_speech(text)
        if not text:
            return False
        with self._lock:
            self._stop_locked()
            self._stop = threading.Event()
            stop = self._stop
            self._worker = threading.Thread(
                target=self._run, args=(text, stop, on_done), daemon=True, name="read-aloud"
            )
            self._worker.start()
        return True

    def read_selection(self) -> bool:
        text = self._selection.selected_text()
        if not text and self._use_clipboard:
            text = self._selection.clipboard_text()
        if not text:
            log.info("Ingen markeret tekst")
            return False
        return self.say(text)

    def toggle(self) -> bool:
        """Læs markeret tekst – eller stop, hvis der allerede læses op."""
        if self.speaking:
            self.stop()
            return False
        return self.read_selection()

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def wait(self, timeout: float | None = None) -> None:
        worker = self._worker
        if worker:
            worker.join(timeout)

    def _stop_locked(self) -> None:
        self._stop.set()
        if self._worker and self._worker is not threading.current_thread():
            self._worker.join(timeout=2)

    def _run(self, text: str, stop: threading.Event, on_done: Callable[[], None] | None) -> None:
        try:
            self._player.play(self._tts.synthesize(text), stop)
        except Exception:
            log.exception("Fejl under oplæsning")
        finally:
            if on_done:
                on_done()
