import threading

from ordhjaelp.services.selection_read import SelectionAutoReader


class Recorder:
    def __init__(self, text: str | None = "hej", accept: bool = True) -> None:
        self.text = text
        self.accept = accept
        self.calls = 0
        self.done = threading.Event()

    def read(self) -> bool:
        self.calls += 1
        self.done.set()
        return self.accept


def test_disabled_does_nothing() -> None:
    rec = Recorder()
    reader = SelectionAutoReader(rec.read, delay=0.01)
    reader.selection_changed()
    assert not rec.done.wait(0.1)
    assert rec.calls == 0


def test_enabled_reads_after_delay() -> None:
    rec = Recorder()
    reader = SelectionAutoReader(rec.read, delay=0.01, enabled=True)
    reader.selection_changed()
    assert rec.done.wait(1)
    assert rec.calls == 1


def test_many_changes_while_dragging_read_once() -> None:
    rec = Recorder()
    reader = SelectionAutoReader(rec.read, delay=0.15, enabled=True)
    for _ in range(10):  # musen trækkes hen over teksten
        reader.selection_changed()
    assert rec.done.wait(1)
    reader.wait()
    assert rec.calls == 1


def test_turning_off_cancels_pending_read() -> None:
    rec = Recorder()
    reader = SelectionAutoReader(rec.read, delay=0.15, enabled=True)
    reader.selection_changed()
    reader.enabled = False
    assert not rec.done.wait(0.3)
    assert rec.calls == 0


def test_errors_in_reading_are_swallowed() -> None:
    called = threading.Event()

    def boom() -> bool:
        called.set()
        raise RuntimeError("fejl")

    reader = SelectionAutoReader(boom, delay=0.01, enabled=True)
    reader.selection_changed()
    assert called.wait(1)
    reader.wait()
    reader.selection_changed()  # virker stadig bagefter
