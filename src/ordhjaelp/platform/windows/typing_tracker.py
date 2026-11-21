"""Ordforslag og læs mens du skriver på Windows: logikken uden ctypes.

Windows har ikke noget som IBus, hvor Ordhjælp selv står for det skrevne ord.
Her går tastetrykkene direkte til programmet, og vi følger med ved siden af:

* Bogstaver lander i programmet som normalt. Vi husker ordet og viser forslag.
* Vælges et forslag, sletter vi det skrevne ord med Backspace og skriver
  forslaget i stedet.
* Kun tasterne til at vælge forslag (↓ ↑ Tab F1–F5 Esc) holdes tilbage fra
  programmet, og kun mens der vises forslag.

Betjeningen er den samme som på Linux (se platform/linux/ibus_engine.py).
Modulet bruger kun standardbiblioteket, så det kan testes på alle systemer.
"""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable

WORD_END = set(" ,.;:!?)\"'")
SENTENCE_END = set(".!?")
PAGE_SIZE = 5


class Key(enum.Enum):
    CHAR = "tegn"  # et tegn, der bliver skrevet (bogstav, tal, mellemrum, tegnsætning)
    BACKSPACE = "backspace"
    ENTER = "enter"
    TAB = "tab"
    ESCAPE = "esc"
    UP = "op"
    DOWN = "ned"
    FUNCTION = "f"  # F1–F5: tag forslag nr. 1–5
    MOVE = "flyt"  # piletaster, Home, Delete …: markøren flytter sig, eller teksten ændres
    SHORTCUT = "genvej"  # Ctrl+C, Alt+Tab osv.


# Virtuelle tastkoder fra Windows (winuser.h)
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_UP = 0x26
VK_DOWN = 0x28
VK_F1 = 0x70
VK_F5 = 0x74
MODIFIER_VKS = {
    0x10, 0x11, 0x12,  # Shift, Ctrl, Alt
    0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5,  # venstre/højre udgaver
    0x5B, 0x5C,  # Windows-tasterne
    0x14, 0x90, 0x91,  # Caps Lock, Num Lock, Scroll Lock
}  # fmt: skip


def classify(
    vk: int, char: str | None, ctrl: bool = False, alt: bool = False, win: bool = False
) -> tuple[Key, str, int] | None:
    """Et tastetryk fra Windows → (tast, tegn, F-nummer). None = ligegyldigt (fx Shift)."""
    if vk in MODIFIER_VKS:
        return None
    alt_gr = ctrl and alt  # AltGr sender Ctrl+Alt: @ £ $ { } osv.
    if win or (ctrl != alt):
        return Key.SHORTCUT, "", 0
    if vk == VK_BACK:
        return Key.BACKSPACE, "", 0
    if vk == VK_TAB:
        return Key.TAB, "", 0
    if vk == VK_RETURN:
        return Key.ENTER, "", 0
    if vk == VK_ESCAPE:
        return Key.ESCAPE, "", 0
    if vk == VK_UP:
        return Key.UP, "", 0
    if vk == VK_DOWN:
        return Key.DOWN, "", 0
    if VK_F1 <= vk <= VK_F5 and not alt_gr:
        return Key.FUNCTION, "", vk - VK_F1 + 1
    if char and char.isprintable():
        return Key.CHAR, char, 0
    return Key.MOVE, "", 0


def _run_now(fn: Callable[[], None]) -> None:
    fn()


class TypingTracker:
    """Følger med i det, eleven skriver, og styrer forslagene.

    :param ask: ord → forslag (spørger Ordhjælp-tjenesten; må gerne tage lidt tid)
    :param tell: send en besked til tjenesten uden at vente på svar
    :param show: vis forslagene; andet argument er det valgte (-1 = intet valgt)
    :param hide: skjul forslagene
    :param replace: slet så mange tegn bagud, og skriv teksten i stedet
    :param run_async: kør noget uden for tastaturtråden (Windows giver kun
        tastaturovervågningen kort tid, før tastetrykket sendes videre)
    """

    def __init__(
        self,
        ask: Callable[[str], list[str]],
        tell: Callable[[dict], None],
        show: Callable[[list[str], int], None],
        hide: Callable[[], None],
        replace: Callable[[int, str], None],
        run_async: Callable[[Callable[[], None]], None] = _run_now,
    ) -> None:
        self._ask = ask
        self._tell = tell
        self._show = show
        self._hide = hide
        self._replace = replace
        self._run_async = run_async
        self._lock = threading.RLock()
        self.word = ""
        self.candidates: list[str] = []
        self.cursor = -1  # det forslag, eleven har valgt med piletasterne (-1 = intet)
        # Til "læs mens du skriver": den igangværende sætning og det seneste ord
        self._sentence = ""
        self._pending_word: str | None = None

    # -- tastetryk -----------------------------------------------------------
    def key(self, key: Key, char: str = "", number: int = 0) -> bool:
        """Et tastetryk. True = tasten skal holdes tilbage fra programmet."""
        with self._lock:
            return self._key(key, char, number)

    def _key(self, key: Key, char: str, number: int) -> bool:
        if key is Key.CHAR and char.isalpha():
            self.word += char
            self.cursor = -1
            self._refresh()
            return False

        if not self.word:
            self._track_without_word(key, char)
            return False

        if key is Key.BACKSPACE:  # programmet sletter selv tegnet
            self.word = self.word[:-1]
            self.cursor = -1
            self._refresh()
            return False
        if key is Key.DOWN and self.candidates:
            self._move(+1)
            return True
        if key is Key.UP and self.candidates:
            self._move(-1)
            return True
        if key is Key.TAB and self.candidates:
            self._commit_word(self._current_candidate())
            return True
        if key is Key.FUNCTION and 0 < number <= len(self.candidates):
            self._commit_word(self.candidates[number - 1])
            return True
        if key is Key.ESCAPE and self.candidates:
            self._clear_candidates()
            return True

        # Mellemrum, tegnsætning, Enter …: afslut ordet. Har eleven valgt et forslag,
        # skal forslaget skrives før tasten, så tasten holdes tilbage og skrives af os.
        if self.cursor >= 0 and key in (Key.CHAR, Key.ENTER):
            after = "\n" if key is Key.ENTER else char
            self._commit_word(self._current_candidate(), after)
            self._track_without_word(key, char)
            return True
        self._commit_word()
        self._track_without_word(key, char)
        return False

    def reset(self) -> None:
        """Markøren er flyttet med musen, eller et andet vindue har fået fokus."""
        with self._lock:
            if self.word and len(self.word) > 1:
                self._learn(self.word)
            self.word = ""
            self._clear_candidates()
            self._forget_sentence()

    def click(self, index: int, right: bool = False) -> None:
        """Klik på et forslag. Højreklik læser ordet op uden at vælge det."""
        with self._lock:
            if not 0 <= index < len(self.candidates):
                return
            candidate = self.candidates[index]
            if right:
                self._say(candidate)
            else:
                self._commit_word(candidate)

    # -- forslag ----------------------------------------------------------------
    def _refresh(self) -> None:
        word = self.word
        if not word:
            self._clear_candidates()
            return

        def lookup() -> None:
            if word != self.word:  # eleven har allerede skrevet videre
                return
            found = self._ask(word)
            self.suggestions_ready(word, found)

        self._run_async(lookup)

    def suggestions_ready(self, word: str, found: list[str]) -> None:
        """Svar fra tjenesten. Et svar på et ord, eleven har skrevet videre på, smides væk."""
        with self._lock:
            if word != self.word:
                return
            self.candidates = [w for w in found if w != word][:PAGE_SIZE]
            self.cursor = -1
            if self.candidates:
                self._show(list(self.candidates), self.cursor)
            else:
                self._hide()

    def _move(self, step: int) -> None:
        if self.cursor < 0:
            self.cursor = 0 if step > 0 else len(self.candidates) - 1
        else:
            self.cursor = (self.cursor + step) % len(self.candidates)
        self._show(list(self.candidates), self.cursor)
        self._say(self._current_candidate())  # hør ordet

    def _current_candidate(self) -> str:
        if not self.candidates:
            return self.word
        return self.candidates[max(self.cursor, 0)]

    def _commit_word(self, text: str | None = None, after: str = "") -> None:
        typed = self.word
        word = text if text is not None else typed
        self.word = ""
        self._clear_candidates()
        if word != typed or after:
            count, new = len(typed), word + after
            self._run_async(lambda: self._replace(count, new))
        if word:
            self._sentence += word
            self._pending_word = word
            if len(word) > 1:
                self._learn(word)

    def _clear_candidates(self) -> None:
        had = bool(self.candidates)
        self.candidates = []
        self.cursor = -1
        if had:
            self._hide()

    # -- læs mens du skriver ----------------------------------------------------
    def _track_without_word(self, key: Key, char: str) -> None:
        """Følg med i tegn uden for ord og meld færdige ord og sætninger til tjenesten.

        Tjenesten afgør ud fra indstillingerne, om der skal læses op.
        """
        if key is Key.ENTER:
            key, char = Key.CHAR, " "
        if key is Key.BACKSPACE:
            self._sentence = self._sentence[:-1]
            self._pending_word = None
            return
        if key is not Key.CHAR:
            # Piletaster, Home, genveje …: markøren flytter sig – start forfra
            self._forget_sentence()
            return
        word, self._pending_word = self._pending_word, None
        self._sentence += char
        sentence = None
        if char in SENTENCE_END:
            sentence, self._sentence = self._sentence.strip(), ""
        if char in WORD_END or sentence:
            request = {"cmd": "skrevet", "ord": word, "saetning": sentence}
            self._run_async(lambda: self._tell(request))

    def _forget_sentence(self) -> None:
        self._sentence = ""
        self._pending_word = None

    def _learn(self, word: str) -> None:
        self._run_async(lambda: self._tell({"cmd": "laer", "ord": word}))

    def _say(self, text: str) -> None:
        self._run_async(lambda: self._tell({"cmd": "sig", "tekst": text}))
