"""Ordforslag og læs mens du skriver på Windows.

Logikken (typing_tracker) testes på alle systemer, overvågningen kun på Windows.
"""

import sys

import pytest

from ordhjaelp.platform.windows.typing_tracker import (
    VK_BACK,
    VK_DOWN,
    VK_F1,
    VK_RETURN,
    Key,
    TypingTracker,
    classify,
)

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="kræver Windows")


class Fake:
    """Optager det, sporeren gør: forslag, indsættelser og beskeder til tjenesten."""

    def __init__(self, suggestions: dict[str, list[str]] | None = None) -> None:
        self.suggestions = suggestions or {}
        self.told: list[dict] = []
        self.shown: list[tuple[list[str], int]] = []
        self.hidden = 0
        self.replaced: list[tuple[int, str]] = []
        self.tracker = TypingTracker(
            ask=lambda word: self.suggestions.get(word, []),
            tell=self.told.append,
            show=lambda c, i: self.shown.append((c, i)),
            hide=self._hide,
            replace=lambda n, text: self.replaced.append((n, text)),
        )

    def _hide(self) -> None:
        self.hidden += 1

    def type(self, text: str) -> list[bool]:
        return [self.tracker.key(Key.CHAR, ch) for ch in text]

    def typed(self, cmd: str) -> list[dict]:
        return [r for r in self.told if r["cmd"] == cmd]


# -- tastetryk → tast ---------------------------------------------------------
def test_classify_letters_space_and_altgr() -> None:
    assert classify(0x41, "a") == (Key.CHAR, "a", 0)
    assert classify(0x20, " ") == (Key.CHAR, " ", 0)
    assert classify(0x32, "@", ctrl=True, alt=True) == (Key.CHAR, "@", 0)  # AltGr+2


def test_classify_special_keys() -> None:
    assert classify(VK_BACK, "\b") == (Key.BACKSPACE, "", 0)
    assert classify(VK_RETURN, "\r") == (Key.ENTER, "", 0)
    assert classify(VK_DOWN, None) == (Key.DOWN, "", 0)
    assert classify(VK_F1 + 2, None) == (Key.FUNCTION, "", 3)
    assert classify(0x25, None) == (Key.MOVE, "", 0)  # venstre pil


def test_classify_shortcuts_and_modifiers() -> None:
    assert classify(0x43, "c", ctrl=True) == (Key.SHORTCUT, "", 0)
    assert classify(0x09, "\t", alt=True) == (Key.SHORTCUT, "", 0)
    assert classify(0x44, "d", win=True) == (Key.SHORTCUT, "", 0)
    assert classify(0xA0, None) is None  # Shift alene


# -- forslag ------------------------------------------------------------------
def test_letters_reach_the_program_and_show_suggestions() -> None:
    fake = Fake({"sk": ["skole", "skal"], "sko": ["skole", "skov"]})
    assert fake.type("sko") == [False, False, False]  # bogstaver holdes aldrig tilbage
    assert fake.tracker.word == "sko"
    assert fake.shown[-1] == (["skole", "skov"], -1)


def test_function_key_replaces_typed_word() -> None:
    fake = Fake({"sgo": ["skole", "skov"]})
    fake.type("sgo")
    assert fake.tracker.key(Key.FUNCTION, number=1) is True
    assert fake.replaced == [(3, "skole")]
    assert fake.tracker.word == ""
    assert {"cmd": "laer", "ord": "skole"} in fake.told


def test_function_key_without_that_many_suggestions_reaches_program() -> None:
    fake = Fake({"sgo": ["skole"]})
    fake.type("sgo")
    assert fake.tracker.key(Key.FUNCTION, number=4) is False


def test_arrows_choose_and_read_aloud_then_tab_takes_it() -> None:
    fake = Fake({"sgo": ["skole", "skov"]})
    fake.type("sgo")
    assert fake.tracker.key(Key.DOWN) is True
    assert fake.tracker.key(Key.DOWN) is True
    assert fake.shown[-1] == (["skole", "skov"], 1)
    assert fake.typed("sig") == [{"cmd": "sig", "tekst": "skole"}, {"cmd": "sig", "tekst": "skov"}]
    assert fake.tracker.key(Key.TAB) is True
    assert fake.replaced == [(3, "skov")]


def test_space_after_choice_writes_suggestion_and_space() -> None:
    fake = Fake({"sgo": ["skole"]})
    fake.type("sgo")
    fake.tracker.key(Key.DOWN)
    assert fake.tracker.key(Key.CHAR, " ") is True  # holdes tilbage og skrives af os
    assert fake.replaced == [(3, "skole ")]


def test_space_without_choice_keeps_what_was_typed() -> None:
    fake = Fake({"sgo": ["skole"]})
    fake.type("sgo")
    assert fake.tracker.key(Key.CHAR, " ") is False
    assert fake.replaced == []
    assert fake.hidden >= 1


def test_keys_without_suggestions_reach_program() -> None:
    fake = Fake()
    fake.type("xyz")
    for key in (Key.DOWN, Key.UP, Key.TAB, Key.ESCAPE):
        assert fake.tracker.key(key) is False


def test_escape_hides_suggestions() -> None:
    fake = Fake({"sk": ["skole"]})
    fake.type("sk")
    assert fake.tracker.key(Key.ESCAPE) is True
    assert fake.tracker.candidates == []
    assert fake.tracker.key(Key.TAB) is False  # intet at vælge, så Tab går videre


def test_backspace_shortens_word_and_asks_again() -> None:
    fake = Fake({"sk": ["skal"], "sko": ["skole"]})
    fake.type("sko")
    assert fake.tracker.key(Key.BACKSPACE) is False  # programmet sletter selv tegnet
    assert fake.tracker.word == "sk"
    assert fake.shown[-1] == (["skal"], -1)


def test_late_answer_for_old_word_is_ignored() -> None:
    fake = Fake()
    fake.type("skol")
    fake.tracker.suggestions_ready("sk", ["skal"])
    assert fake.tracker.candidates == []


def test_typed_word_is_not_suggested() -> None:
    fake = Fake({"skole": ["skole", "skoler"]})
    fake.type("skole")
    assert fake.tracker.candidates == ["skoler"]


def test_click_takes_suggestion_and_right_click_reads_it() -> None:
    fake = Fake({"sgo": ["skole", "skov"]})
    fake.type("sgo")
    fake.tracker.click(1, right=True)
    assert fake.typed("sig") == [{"cmd": "sig", "tekst": "skov"}]
    assert fake.replaced == []
    fake.tracker.click(0)
    assert fake.replaced == [(3, "skole")]


def test_reset_forgets_word_and_sentence() -> None:
    fake = Fake({"sk": ["skole"]})
    fake.type("Hej sk")
    fake.tracker.reset()
    assert fake.tracker.word == ""
    assert fake.tracker.candidates == []
    fake.type("Ja.")
    assert fake.typed("skrevet")[-1]["saetning"] == "Ja."


# -- læs mens du skriver ----------------------------------------------------------
def test_reports_words_and_sentences() -> None:
    fake = Fake()
    fake.type("Jeg er glad.")
    reports = fake.typed("skrevet")
    assert [r["ord"] for r in reports] == ["Jeg", "er", "glad"]
    assert reports[-1]["saetning"] == "Jeg er glad."


def test_reports_chosen_suggestion_as_word() -> None:
    fake = Fake({"sgo": ["skole"]})
    fake.type("min sgo")
    fake.tracker.key(Key.FUNCTION, number=1)
    fake.type(" ")
    assert fake.typed("skrevet")[-1]["ord"] == "skole"


def test_enter_ends_word_and_arrow_starts_over() -> None:
    fake = Fake()
    fake.type("hej")
    fake.tracker.key(Key.ENTER)
    assert fake.typed("skrevet")[-1]["ord"] == "hej"
    fake.type("halv")
    fake.tracker.key(Key.MOVE)
    fake.type("hel.")
    assert fake.typed("skrevet")[-1]["saetning"] == "hel."


def test_shortcut_ends_word_without_reading_it() -> None:
    fake = Fake()
    fake.type("hej")
    assert fake.tracker.key(Key.SHORTCUT) is False
    assert fake.typed("skrevet") == []
    assert fake.tracker.word == ""


# -- Windows-delen --------------------------------------------------------------
def test_typing_setup_has_no_system_settings() -> None:
    from ordhjaelp.platform.windows.typing import WindowsTypingSetup

    setup = WindowsTypingSetup()
    assert setup.settings_button is None
    assert setup.open_settings() is False
    assert [c.label for c in setup.checks()] == ["Ordhjælp lytter efter tastetryk"]


def test_backspace_inputs_are_marked() -> None:
    from ordhjaelp.platform.windows import win32

    items = win32.backspace_inputs(2, extra=7)
    assert [i.u.ki.wVk for i in items] == [win32.VK_BACK] * 4
    assert all(i.u.ki.dwExtraInfo == 7 for i in items)
    assert all(i.u.ki.dwExtraInfo == 7 for i in win32.unicode_inputs("a\n", extra=7))


@windows_only
def test_hook_struct_sizes_match_windows() -> None:
    import ctypes

    from ordhjaelp.platform.windows import win32

    assert ctypes.sizeof(win32.KBDLLHOOKSTRUCT) == 24
    assert ctypes.sizeof(win32.MSLLHOOKSTRUCT) == 32
    assert ctypes.sizeof(win32.GUITHREADINFO) == 72


@windows_only
def test_input_method_starts_listening_and_stops(monkeypatch) -> None:
    import ordhjaelp.platform.windows.typing as typing_mod
    from ordhjaelp.platform import get_input_method, get_typing_setup

    monkeypatch.setattr(typing_mod, "_make_popup", lambda: None)
    method = get_input_method()
    assert method.start() is True
    try:
        assert all(check.ok for check in get_typing_setup().checks())
    finally:
        method.stop()
    assert not any(check.ok for check in get_typing_setup().checks())


@windows_only
def test_layout_turns_keys_into_characters() -> None:
    from ordhjaelp.platform.windows.typing import _to_char

    assert _to_char(0x41, 0x1E, ctrl=False, alt=False) in ("a", "A")  # A-tasten
    assert _to_char(0x20, 0x39, ctrl=False, alt=False) == " "
