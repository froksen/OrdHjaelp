"""Læs ved markering og læs under musen på Windows.

Reglerne for, hvornår noget er markeret, testes på alle systemer. UI Automation
og overvågningen kun på Windows.
"""

import sys

import pytest

from ordhjaelp.platform.windows.gestures import SelectionGestures

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="kræver Windows")


# -- hvornår har eleven markeret noget? ------------------------------------------
def test_drag_selects() -> None:
    g = SelectionGestures(double_click_ms=500)
    g.mouse_down(100, 100, 0)
    assert g.mouse_up(180, 102, 300) is True


def test_single_click_does_not_select() -> None:
    g = SelectionGestures(double_click_ms=500)
    g.mouse_down(100, 100, 0)
    assert g.mouse_up(101, 100, 80) is False


def test_double_and_triple_click_select() -> None:
    g = SelectionGestures(double_click_ms=500)
    g.mouse_down(100, 100, 0)
    assert g.mouse_up(100, 100, 50) is False
    g.mouse_down(100, 100, 200)
    assert g.mouse_up(100, 100, 250) is True  # dobbeltklik: ordet
    g.mouse_down(101, 100, 400)
    assert g.mouse_up(101, 100, 450) is True  # trippelklik: linjen


def test_slow_or_distant_second_click_is_not_a_double_click() -> None:
    g = SelectionGestures(double_click_ms=500)
    g.mouse_down(100, 100, 0)
    g.mouse_up(100, 100, 50)
    g.mouse_down(100, 100, 900)  # for langsomt
    assert g.mouse_up(100, 100, 950) is False
    g.mouse_down(140, 100, 1000)  # for langt væk
    assert g.mouse_up(140, 100, 1050) is False


def test_up_without_down_is_ignored() -> None:
    assert SelectionGestures().mouse_up(1, 1, 1) is False


def test_keyboard_selection() -> None:
    left, end, a = 0x25, 0x23, 0x41
    assert SelectionGestures.key(left, shift=True, ctrl=False, alt=False)
    assert SelectionGestures.key(end, shift=True, ctrl=True, alt=False)  # Ctrl+Shift+End
    assert SelectionGestures.key(a, shift=False, ctrl=True, alt=False)  # Ctrl+A
    assert not SelectionGestures.key(left, shift=False, ctrl=False, alt=False)
    assert not SelectionGestures.key(a, shift=False, ctrl=False, alt=False)
    assert not SelectionGestures.key(left, shift=True, ctrl=False, alt=True)


# -- læs under musen ----------------------------------------------------------------
def test_pointer_text_uses_shared_word_and_sentence_rules(monkeypatch) -> None:
    from ordhjaelp.platform.windows import pointer, typing, uia

    text = "Hunden løb hjem. Katten sov på sofaen!"
    offset = text.index("sofaen") + 2
    calls = []

    def fake_at_point(x, y, following=False, max_chars=0):  # noqa: ANN001, ANN202
        calls.append(following)
        return text, offset

    monkeypatch.setattr(typing, "mouse_position", lambda: (10, 20))
    monkeypatch.setattr(uia, "text_at_point", fake_at_point)
    provider = pointer.WindowsPointerText()
    assert provider.text_at_pointer("ord") == "sofaen"
    assert provider.text_at_pointer("saetning") == "Katten sov på sofaen!"
    assert provider.text_at_pointer("herfra") == "sofaen!"
    assert calls == [False, False, True]  # kun "herfra" beder om resten af teksten


def test_pointer_text_none_without_text(monkeypatch) -> None:
    from ordhjaelp.platform.windows import pointer, typing, uia

    monkeypatch.setattr(typing, "mouse_position", lambda: (0, 0))
    monkeypatch.setattr(uia, "text_at_point", lambda *a, **k: None)
    assert pointer.WindowsPointerText().text_at_pointer("ord") is None


def test_platform_offers_pointer_text_on_windows(monkeypatch) -> None:
    from ordhjaelp import platform

    if sys.platform != "win32":
        pytest.skip("kræver Windows")
    assert type(platform.get_pointer_text()).__name__ == "WindowsPointerText"


# -- kun på Windows ---------------------------------------------------------------------
@windows_only
def test_uia_guid_layout() -> None:
    import ctypes

    from ordhjaelp.platform.windows import uia

    assert ctypes.sizeof(uia.GUID) == 16
    guid = uia.GUID.parse(uia.IID_IUIAUTOMATION)
    assert guid.Data1 == 0x30CBE57D


@windows_only
def test_uia_answers_without_hanging() -> None:
    from ordhjaelp.platform.windows import uia

    # Uanset hvad der har fokus: et svar (eller None) inden for tidsgrænsen, ingen fejl
    result = uia.selected_text()
    assert result is None or isinstance(result, str)


@windows_only
def test_gesture_watcher_starts_and_stops() -> None:
    from ordhjaelp.platform.windows.gestures import GestureWatcher

    watcher = GestureWatcher(lambda: None)
    assert watcher.start() is True
    watcher.stop()


def test_timeout_gives_none() -> None:
    import threading

    from ordhjaelp.platform.windows import uia

    release = threading.Event()
    assert uia.run_with_timeout(lambda: release.wait(5), timeout=0.05) is None
    release.set()
    assert uia.run_with_timeout(lambda: 42) == 42
    assert uia.run_with_timeout(lambda: 1 / 0) is None
