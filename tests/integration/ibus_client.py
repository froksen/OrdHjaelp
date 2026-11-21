"""Integrationstest: send tastetryk til Ordhjælp-motoren via en privat IBus-instans."""

import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus()
assert bus.is_connected(), "ingen forbindelse til privat ibus"
for _ in range(300):  # op til 30 s – første start af ibus-daemon er langsom
    if bus.name_has_owner("dk.ordhjaelp.IBus") and bus.set_global_engine("ordhjaelp"):
        break
    time.sleep(0.1)
else:
    raise SystemExit("Ordhjælp-motoren blev aldrig klar")
ctx = bus.create_input_context("ordhjaelp-test")
ctx.set_capabilities(
    IBus.Capabilite.PREEDIT_TEXT | IBus.Capabilite.LOOKUP_TABLE | IBus.Capabilite.FOCUS
)
committed, tables = [], []
ctx.connect("commit-text", lambda c, t: committed.append(t.get_text()))
ctx.connect(
    "update-lookup-table",
    lambda c, t, v: tables.append(
        [t.get_candidate(i).get_text() for i in range(t.get_number_of_candidates())]
    ),
)
ctx.focus_in()
loop = GLib.MainContext.default()


def pump(n=30):
    for _ in range(n):
        loop.iteration(False)
        time.sleep(0.01)


pump(50)
e = ctx.get_engine()
print("motor:", e.get_name() if e else None)


def key(keyval, state=0):
    ctx.process_key_event(keyval, 0, state)
    pump()
    ctx.process_key_event(keyval, 0, state | IBus.ModifierType.RELEASE_MASK)
    pump()


def typ(s):
    for ch in s:
        key(IBus.unicode_to_keyval(ch))


# 1) skriv "sgole" + mellemrum uden at vælge: det skrevne bliver stående
typ("sgole")
print("forslag:", tables[-1] if tables else None)
key(IBus.KEY_space)
# 2) skriv "sgole", ↓ vælger første forslag, mellemrum tager det
typ("sgole")
key(IBus.KEY_Down)
key(IBus.KEY_space)
# 3) skriv "vordan" + Tab = første forslag
typ("vordan")
key(IBus.KEY_Tab)
# 4) F2 vælger forslag nr. 2
typ("fotbol")
key(IBus.KEY_F2)
# 5) backspace retter i ordet
typ("hejx")
key(IBus.KEY_BackSpace)
key(IBus.KEY_space)
# 6) Stort begyndelsesbogstav + æøå
typ("Køben")
key(IBus.KEY_Tab)
print("skrevet:", committed)
