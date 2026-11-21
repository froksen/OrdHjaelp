import threading

import numpy as np

from ordhjaelp.services.dictation import (
    MSG_ERROR,
    MSG_NOTHING_HEARD,
    DictationService,
    DictationState,
)

ONE_SECOND = np.zeros(16000, dtype=np.float32)


class FakeRecorder:
    def __init__(self, audio=ONE_SECOND, fail=False):
        self.audio, self.fail = audio, fail
        self.on_limit_reached = None
        self.started = False

    def start(self):
        if self.fail:
            raise OSError("ingen mikrofon")
        self.started = True

    def stop(self):
        return self.audio


class FakeTranscriber:
    def __init__(self, text="Hej med dig.", fail=False):
        self.text, self.fail = text, fail

    def transcribe(self, audio):
        if self.fail:
            raise RuntimeError("model fejlede")
        return self.text


class FakeInjector:
    def __init__(self):
        self.inserted = []

    def insert(self, text):
        self.inserted.append(text)


def make(recorder=None, transcriber=None):
    injector, said, events, stopped = FakeInjector(), [], [], []
    svc = DictationService(
        recorder or FakeRecorder(),
        transcriber or FakeTranscriber(),
        injector,
        before_recording=lambda: stopped.append(True),
        tell_user=said.append,
    )
    svc.add_listener(events.append)
    return svc, injector, said, events, stopped


def test_full_cycle_inserts_text_with_space() -> None:
    svc, injector, said, events, stopped = make()
    assert svc.toggle() is DictationState.RECORDING
    assert stopped == [True]  # oplæsning stoppes før optagelse
    assert svc.toggle() is DictationState.TRANSCRIBING
    svc.wait(2)
    assert injector.inserted == ["Hej med dig. "]
    assert said == []
    assert events == [DictationState.RECORDING, DictationState.TRANSCRIBING, DictationState.IDLE]


def test_click_while_transcribing_is_ignored() -> None:
    release = threading.Event()

    class SlowTranscriber(FakeTranscriber):
        def transcribe(self, audio):
            release.wait(2)
            return super().transcribe(audio)

    svc, injector, *_ = make(transcriber=SlowTranscriber())
    svc.toggle()
    svc.toggle()
    assert svc.toggle() is DictationState.TRANSCRIBING  # klik ignoreres
    release.set()
    svc.wait(2)
    assert svc.state is DictationState.IDLE
    assert injector.inserted == ["Hej med dig. "]


def test_nothing_heard() -> None:
    svc, injector, said, *_ = make(transcriber=FakeTranscriber(text="  "))
    svc.toggle()
    svc.toggle()
    svc.wait(2)
    assert injector.inserted == []
    assert said == [MSG_NOTHING_HEARD]


def test_too_short_recording_is_silent() -> None:
    svc, injector, said, *_ = make(recorder=FakeRecorder(audio=np.zeros(100, dtype=np.float32)))
    svc.toggle()
    svc.toggle()
    svc.wait(2)
    assert injector.inserted == [] and said == []
    assert svc.state is DictationState.IDLE


def test_transcription_error_tells_user() -> None:
    svc, injector, said, *_ = make(transcriber=FakeTranscriber(fail=True))
    svc.toggle()
    svc.toggle()
    svc.wait(2)
    assert said == [MSG_ERROR]
    assert svc.state is DictationState.IDLE


def test_microphone_error_tells_user() -> None:
    svc, _, said, events, _ = make(recorder=FakeRecorder(fail=True))
    assert svc.toggle() is DictationState.IDLE
    assert said == [MSG_ERROR]
    assert events == []


def test_time_limit_finishes_recording() -> None:
    rec = FakeRecorder()
    svc, injector, *_ = make(recorder=rec)
    svc.toggle()
    rec.on_limit_reached()  # optageren melder: 2 minutter nået
    svc.wait(2)
    assert injector.inserted == ["Hej med dig. "]
