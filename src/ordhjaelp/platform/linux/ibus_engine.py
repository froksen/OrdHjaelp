#!/usr/bin/python3
"""Ordhjælp som IBus-indtastningsmetode: ordforslag i alle programmer.

Kører med *systemets* Python (som har IBus-bindingerne via python3-gobject) og
bruger kun standardbiblioteket derudover. Selve forslagene kommer fra
Ordhjælp-tjenesten over den lokale IPC-forbindelse – denne fil er bevidst tynd.

Betjening:
  skriv          ordet vises understreget, forslag vises ved markøren
  ↓ / ↑          vælg forslag (det valgte læses op)
  Tab, mellemrum tag det valgte forslag (uden valg: det skrevne bliver stående)
  F1–F5 / klik   tag forslag nr. 1–5
  højreklik      læs forslaget op uden at vælge det
  Esc            skjul forslagene

Læs mens du skriver (slås til i indstillingerne): motoren melder færdige ord
(ved mellemrum/tegn) og sætninger (ved . ! ?) til tjenesten.
"""

from __future__ import annotations

import os
import sys
import threading
from multiprocessing.connection import Client
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

ENGINE_NAME = "ordhjaelp"
COMPONENT_NAME = "dk.ordhjaelp.IBus"
MOUSE_RIGHT = 3
WORD_END = set(" ,.;:!?)\"'")
SENTENCE_END = set(".!?")
PAGE_SIZE = 5
MODIFIER_KEYS = {
    IBus.KEY_Shift_L,
    IBus.KEY_Shift_R,
    IBus.KEY_Control_L,
    IBus.KEY_Control_R,
    IBus.KEY_Alt_L,
    IBus.KEY_Alt_R,
    IBus.KEY_Super_L,
    IBus.KEY_Super_R,
    IBus.KEY_Meta_L,
    IBus.KEY_Meta_R,
    IBus.KEY_Caps_Lock,
    IBus.KEY_ISO_Level3_Shift,
    IBus.KEY_Num_Lock,
}
FUNCTION_KEYS = [IBus.KEY_F1, IBus.KEY_F2, IBus.KEY_F3, IBus.KEY_F4, IBus.KEY_F5]
SHORTCUT_MASK = (
    IBus.ModifierType.CONTROL_MASK
    | IBus.ModifierType.MOD1_MASK
    | IBus.ModifierType.SUPER_MASK
    | IBus.ModifierType.MOD4_MASK
)


# -- forbindelse til Ordhjælp-tjenesten (samme protokol som ordhjaelp.ipc) ----
def _address() -> str:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return str(Path(runtime) / "ordhjaelp.sock")


def _authkey() -> bytes | None:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    try:
        return (Path(base) / "ordhjaelp" / "ipc.key").read_bytes()
    except OSError:
        return None


def ask(request: dict, timeout: float = 0.5) -> dict | None:
    key = _authkey()
    if key is None:
        return None
    try:
        with Client(_address(), authkey=key) as conn:
            conn.send(request)
            if conn.poll(timeout):
                return conn.recv()
    except Exception:  # noqa: BLE001 - uden tjenesten virker tastaturet bare normalt
        return None
    return None


def tell(request: dict) -> None:
    """Send uden at vente på svar (fx 'husk dette ord')."""
    threading.Thread(target=ask, args=(request,), daemon=True).start()


# -- selve indtastningsmetoden ------------------------------------------------
class OrdhjaelpEngine(IBus.Engine):
    __gtype_name__ = "OrdhjaelpEngine"

    def __init__(self, bus: IBus.Bus, object_path: str) -> None:
        super().__init__(
            engine_name=ENGINE_NAME, connection=bus.get_connection(), object_path=object_path
        )
        self._word = ""
        self._candidates: list[str] = []
        self._chosen = False  # har eleven selv valgt et forslag med piletasterne?
        # Til "læs mens du skriver": den igangværende sætning og det seneste ord
        self._sentence = ""
        self._pending_word: str | None = None
        self._table = IBus.LookupTable.new(PAGE_SIZE, 0, False, False)
        self._table.set_orientation(IBus.Orientation.VERTICAL)

    # Tastetryk ------------------------------------------------------------
    def do_process_key_event(self, keyval: int, keycode: int, state: int) -> bool:
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        if keyval in MODIFIER_KEYS:
            return False
        if state & SHORTCUT_MASK:  # Ctrl+C, Alt+Tab osv. – lad programmet få dem
            self._commit_word()
            return False

        char = IBus.keyval_to_unicode(keyval)
        if char and char.isalpha():
            self._word += char
            self._chosen = False
            self._refresh()
            return True

        if not self._word:
            self._track_without_word(keyval, char)
            return False

        if keyval == IBus.KEY_BackSpace:
            self._word = self._word[:-1]
            self._chosen = False
            self._refresh()
            return True
        if keyval in (IBus.KEY_Down, IBus.KEY_KP_Down) and self._candidates:
            self._move(+1)
            return True
        if keyval in (IBus.KEY_Up, IBus.KEY_KP_Up) and self._candidates:
            self._move(-1)
            return True
        if keyval == IBus.KEY_Tab and self._candidates:
            self._commit_word(self._current_candidate())
            return True
        if keyval in FUNCTION_KEYS:
            index = FUNCTION_KEYS.index(keyval)
            if index < len(self._candidates):
                self._commit_word(self._candidates[index])
                return True
        if keyval == IBus.KEY_Escape:
            self._candidates = []
            self._chosen = False
            self.hide_lookup_table()
            return True

        # Mellemrum, tegnsætning, Enter, piletaster …: afslut ordet og send tasten videre
        self._commit_word(self._current_candidate() if self._chosen else None)
        self._track_without_word(keyval, char)
        return False

    def do_candidate_clicked(self, index: int, button: int, state: int) -> None:
        position = self._table.get_cursor_pos() // PAGE_SIZE * PAGE_SIZE + index
        if position >= len(self._candidates):
            return
        candidate = self._candidates[position]
        if button == MOUSE_RIGHT:
            # Højreklik: hør ordet uden at vælge det (IBus-panelet melder ikke "mus over")
            tell({"cmd": "sig", "tekst": candidate})
        else:
            self._commit_word(candidate)

    def do_focus_out(self) -> None:
        self._commit_word()
        self._forget_sentence()

    def do_reset(self) -> None:
        self._commit_word()

    def do_disable(self) -> None:
        self._commit_word()

    # Læs mens du skriver ---------------------------------------------------
    def _track_without_word(self, keyval: int, char: str) -> None:
        """Følg med i tegn uden for ord og meld færdige ord/sætninger til tjenesten.

        Tjenesten afgør ud fra indstillingerne, om der skal læses op.
        """
        if keyval in (IBus.KEY_Return, IBus.KEY_KP_Enter):
            char = " "
        if keyval == IBus.KEY_BackSpace:
            self._sentence = self._sentence[:-1]
            self._pending_word = None
            return
        if not char or not char.isprintable():
            # Piletaster, Home, Delete …: markøren flytter sig – start forfra
            self._forget_sentence()
            return
        word, self._pending_word = self._pending_word, None
        self._sentence += char
        sentence = None
        if char in SENTENCE_END:
            sentence, self._sentence = self._sentence.strip(), ""
        if char in WORD_END or sentence:
            tell({"cmd": "skrevet", "ord": word, "saetning": sentence})

    def _forget_sentence(self) -> None:
        self._sentence = ""
        self._pending_word = None

    # Hjælpere -------------------------------------------------------------
    def _refresh(self) -> None:
        word = self._word
        if not word:
            self._clear()
            return
        text = IBus.Text.new_from_string(word)
        attrs = IBus.AttrList()
        attrs.append(
            IBus.Attribute.new(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, 0, len(word))
        )
        text.set_attributes(attrs)
        self.update_preedit_text(text, len(word), True)

        reply = ask({"cmd": "forslag", "ord": word}) or {}
        self._candidates = [w for w in reply.get("forslag", []) if w != word][:PAGE_SIZE]
        self._table.clear()
        self._table.set_cursor_visible(False)
        for i, candidate in enumerate(self._candidates):
            self._table.append_candidate(IBus.Text.new_from_string(candidate))
            self._table.set_label(i, IBus.Text.new_from_string(f"F{i + 1} "))
        if self._candidates:
            self.update_lookup_table(self._table, True)
        else:
            self.hide_lookup_table()

    def _move(self, step: int) -> None:
        if not self._chosen:
            self._chosen = True
            self._table.set_cursor_pos(0 if step > 0 else len(self._candidates) - 1)
        elif step > 0:
            self._table.cursor_down()
        else:
            self._table.cursor_up()
        self._table.set_cursor_visible(True)
        self.update_lookup_table(self._table, True)
        tell({"cmd": "sig", "tekst": self._current_candidate()})  # hør ordet

    def _current_candidate(self) -> str:
        if not self._candidates:
            return self._word
        return self._candidates[self._table.get_cursor_pos() % len(self._candidates)]

    def _commit_word(self, text: str | None = None) -> None:
        word = text if text is not None else self._word
        self._clear()
        if word:
            self.commit_text(IBus.Text.new_from_string(word))
            self._sentence += word
            self._pending_word = word
            if len(word) > 1:
                tell({"cmd": "laer", "ord": word})

    def _clear(self) -> None:
        self._word = ""
        self._candidates = []
        self._chosen = False
        self._table.clear()
        self.hide_lookup_table()
        self.update_preedit_text(IBus.Text.new_from_string(""), 0, False)


def main() -> int:
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("IBus kører ikke", file=sys.stderr)
        return 1
    factory = IBus.Factory.new(bus.get_connection())
    engines: list[OrdhjaelpEngine] = []  # behold referencer, så de ikke ryddes væk

    def create_engine(_factory: IBus.Factory, name: str) -> OrdhjaelpEngine | None:
        if name != ENGINE_NAME:
            return None
        engine = OrdhjaelpEngine(bus, f"/org/freedesktop/IBus/Engine/Ordhjaelp/{len(engines)}")
        engines.append(engine)
        return engine

    factory.connect("create-engine", create_engine)

    component = IBus.Component(
        name=COMPONENT_NAME,
        description="Ordhjælp – dansk ordforslag",
        version="0.1",
        license="GPL-3.0-or-later",
        author="Ordhjælp",
        homepage="",
        command_line="",
        textdomain="",
    )
    component.add_engine(
        IBus.EngineDesc(
            name=ENGINE_NAME,
            longname="Ordhjælp (dansk ordforslag)",
            description="Ordforslag til danske elever – også ved lydret stavning",
            language="da",
            license="GPL-3.0-or-later",
            author="Ordhjælp",
            icon="accessories-text-editor",
            layout="default",
            rank=0,
        )
    )
    # IBus finder fabrikken via komponentens D-Bus-navn
    bus.request_name(COMPONENT_NAME, 0)
    bus.register_component(component)
    if "--aktiver" in sys.argv:
        bus.set_global_engine_async(ENGINE_NAME, -1, None, None, None)

    loop = GLib.MainLoop()
    bus.connect("disconnected", lambda *_: loop.quit())
    loop.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
