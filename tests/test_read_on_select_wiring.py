from ordhjaelp.daemon import _make_read_on_select


class FakeSelection:
    def __init__(self, supported: bool = True) -> None:
        self.supported = supported
        self.callbacks: list = []

    def on_change(self, callback) -> bool:
        if self.supported:
            self.callbacks.append(callback)
        return self.supported


class FakeService:
    def read_new_selection(self) -> bool:
        return True


def test_listens_only_after_turned_on_and_only_once() -> None:
    sel = FakeSelection()
    set_enabled = _make_read_on_select(sel, FakeService())
    assert sel.callbacks == []  # slået fra: ingen overvågning
    set_enabled(True)
    set_enabled(False)
    set_enabled(True)
    assert len(sel.callbacks) == 1


def test_unsupported_platform_stays_off() -> None:
    sel = FakeSelection(supported=False)
    set_enabled = _make_read_on_select(sel, FakeService())
    set_enabled(True)
    assert sel.callbacks == []
