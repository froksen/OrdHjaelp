import threading
from collections.abc import Iterable

import numpy as np

from ordhjaelp.services.read_aloud import ReadAloudService
from ordhjaelp.tts.piper_engine import SpeechChunk


class FakeTTS:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def synthesize(self, text: str) -> Iterable[SpeechChunk]:
        self.texts.append(text)
        yield SpeechChunk(audio=np.zeros(10, dtype=np.int16), sample_rate=22050)


class FakePlayer:
    """Spiller 'for evigt', indtil der bliver trykket stop."""

    def __init__(self, block: bool = False) -> None:
        self.block = block
        self.started = threading.Event()

    def play(self, chunks: Iterable[SpeechChunk], stop: threading.Event) -> None:
        list(chunks)
        self.started.set()
        if self.block:
            stop.wait(5)


class FakeSelection:
    def __init__(self, selected: str | None, clipboard: str | None = None) -> None:
        self.selected, self.clipboard = selected, clipboard

    def selected_text(self) -> str | None:
        return self.selected

    def clipboard_text(self) -> str | None:
        return self.clipboard


def make(selected=None, clipboard=None, block=False, fallback=True):
    tts, player = FakeTTS(), FakePlayer(block)
    svc = ReadAloudService(tts, player, FakeSelection(selected, clipboard), fallback)
    return svc, tts, player


def test_reads_selection_normalized() -> None:
    svc, tts, _ = make("Hej\n  verden")
    assert svc.read_selection()
    svc.wait(2)
    assert tts.texts == ["Hej verden"]


def test_falls_back_to_clipboard() -> None:
    svc, tts, _ = make(None, "fra udklipsholder")
    assert svc.read_selection()
    svc.wait(2)
    assert tts.texts == ["fra udklipsholder"]


def test_no_fallback_when_disabled() -> None:
    svc, tts, _ = make(None, "fra udklipsholder", fallback=False)
    assert not svc.read_selection()
    assert tts.texts == []


def test_nothing_selected() -> None:
    svc, _, _ = make(None, None)
    assert not svc.read_selection()
    assert not svc.speaking


def test_toggle_stops_while_speaking() -> None:
    svc, _, player = make("lang tekst", block=True)
    assert svc.toggle()
    assert player.started.wait(2)
    assert svc.speaking
    assert not svc.toggle()  # andet tryk stopper
    svc.wait(2)
    assert not svc.speaking


def test_new_text_interrupts_old() -> None:
    svc, tts, player = make(block=True)
    svc.say("første")
    assert player.started.wait(2)
    svc.say("anden")
    svc.stop()
    svc.wait(2)
    assert tts.texts == ["første", "anden"]
