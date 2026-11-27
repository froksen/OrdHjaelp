"""Tjenesten 'diktér' – uafhængig af styresystem.

Klik én gang: optagelse starter. Klik igen: teksten genkendes og skrives ind,
hvor markøren står.
"""

from __future__ import annotations

import enum
import logging
import threading
from collections.abc import Callable
from typing import Protocol

import numpy as np

from ordhjaelp.platform.base import TextInjector

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MIN_SECONDS = 0.4  # kortere end dette regnes for et fejlklik

MSG_NOTHING_HEARD = "Jeg hørte ikke noget. Prøv igen."
MSG_ERROR = "Dikteringen virkede ikke. Prøv igen."


class DictationState(enum.Enum):
    IDLE = "klar"
    RECORDING = "optager"
    TRANSCRIBING = "skriver"


class Recorder(Protocol):
    on_limit_reached: Callable[[], None] | None

    def start(self) -> None: ...
    def stop(self) -> np.ndarray: ...


class Transcriber(Protocol):
    def transcribe(self, audio: np.ndarray) -> str: ...


class SoundCues(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class DictationService:
    def __init__(
        self,
        recorder: Recorder,
        transcriber: Transcriber,
        injector: TextInjector,
        cues: SoundCues | None = None,
        before_recording: Callable[[], None] | None = None,
        tell_user: Callable[[str], None] | None = None,
    ) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._injector = injector
        self._cues = cues
        self._before_recording = before_recording
        self._tell_user = tell_user
        self._state = DictationState.IDLE
        self._lock = threading.Lock()
        self._listeners: list[Callable[[DictationState], None]] = []
        self._worker: threading.Thread | None = None

    @property
    def state(self) -> DictationState:
        return self._state

    def add_listener(self, callback: Callable[[DictationState], None]) -> None:
        """Kaldes ved hver tilstandsændring (fra en baggrundstråd)."""
        self._listeners.append(callback)

    def toggle(self) -> DictationState:
        """Start eller stop optagelse. Returnerer den tilstand, der blev skiftet til."""
        with self._lock:
            if self._state is DictationState.IDLE:
                self._start_locked()
                return self._state  # RECORDING, eller IDLE hvis mikrofonen fejlede
            if self._state is DictationState.RECORDING:
                self._finish_locked()
                return DictationState.TRANSCRIBING
            return self._state  # TRANSCRIBING: ignorér klik, til teksten er skrevet

    def finish(self) -> None:
        with self._lock:
            if self._state is DictationState.RECORDING:
                self._finish_locked()

    def insert_text(self, text: str) -> None:
        """Skriv tekst direkte (bruges til fejlfinding)."""
        self._injector.insert(text)

    def wait(self, timeout: float | None = None) -> None:
        if self._worker:
            self._worker.join(timeout)

    # -- intern ---------------------------------------------------------
    def _start_locked(self) -> None:
        if self._before_recording:
            self._before_recording()  # fx stop oplæsning, så den ikke bliver optaget
        if self._cues:
            self._cues.start()
        try:
            self._recorder.on_limit_reached = self.finish
            self._recorder.start()
        except Exception:
            log.exception("Kunne ikke starte optagelse")
            self._say(MSG_ERROR)
            return
        self._set(DictationState.RECORDING)

    def _finish_locked(self) -> None:
        audio = self._recorder.stop()
        if self._cues:
            self._cues.stop()
        self._set(DictationState.TRANSCRIBING)
        self._worker = threading.Thread(
            target=self._transcribe_and_insert, args=(audio,), daemon=True, name="dictation"
        )
        self._worker.start()

    def _transcribe_and_insert(self, audio: np.ndarray) -> None:
        try:
            if len(audio) < MIN_SECONDS * SAMPLE_RATE:
                log.info("Optagelsen var for kort")
                return
            text = self._transcriber.transcribe(audio).strip()
            # Selve teksten kun ved fejlfinding (-v): loggen må ikke gemme elevens tekst
            log.info("Dikteret %d tegn", len(text))
            log.debug("Dikteret: %r", text)
            if not text:
                self._say(MSG_NOTHING_HEARD)
                return
            self._injector.insert(text + " ")
        except Exception:
            log.exception("Fejl under diktering")
            self._say(MSG_ERROR)
        finally:
            self._set(DictationState.IDLE)

    def _say(self, message: str) -> None:
        if self._tell_user:
            try:
                self._tell_user(message)
            except Exception:
                log.exception("Kunne ikke give besked til brugeren")

    def _set(self, state: DictationState) -> None:
        self._state = state
        for callback in self._listeners:
            try:
                callback(state)
            except Exception:
                log.exception("Fejl i lytter")
