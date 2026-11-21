"""Et lille GTK-vindue med kendt dansk tekst til AT-SPI-testen (kører med systemets Python)."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

PARAGRAPHS = [
    "Hunden løb hjem. Den var træt! Så sov den.",
    "Næste afsnit kommer her.",
    "Og det sidste afsnit.",
]

window = Gtk.Window(title="Ordhjælp testvindue")
window.move(0, 0)
window.set_default_size(800, 300)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
for text in PARAGRAPHS:
    label = Gtk.Label(label=text, xalign=0)
    label.set_selectable(True)
    box.pack_start(label, False, False, 10)
window.add(box)
window.connect("destroy", Gtk.main_quit)
window.show_all()
Gtk.main()
