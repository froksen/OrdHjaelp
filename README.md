# Ordhjælp

Dansk læse- og skrivehjælp (LST) til Linux – gratis, open source og offline.
Senere også Windows og macOS.

**Fase 1 (nu):** Markér tekst hvor som helst, tryk **Ctrl+Alt+L**, og teksten
læses op med en naturlig dansk stemme. Tryk igen (eller **Ctrl+Alt+S**) for at stoppe.

## Kom i gang (Fedora/KDE)

```bash
sudo dnf install wl-clipboard portaudio      # markeret tekst + lyd
pip install --user uv                        # projektværktøj
cd ~/Udvikling/LST
uv sync                                      # installerer afhængigheder
uv run ordhjaelp installer --autostart       # menu + start ved login
uv run ordhjaelp start                       # første gang: godkend genvejene i KDE-dialogen
```

Stemmen (ca. 60 MB) hentes automatisk første gang.

## Kommandoer

| Kommando | Hvad den gør |
|---|---|
| `ordhjaelp start` | Starter tjenesten (holder stemmen klar og lytter efter genveje) |
| `ordhjaelp laes` | Læser markeret tekst op – eller stopper, hvis der læses |
| `ordhjaelp stop` | Stopper oplæsning |
| `ordhjaelp sig "tekst"` | Læser en tekst op |
| `ordhjaelp status` | Viser om tjenesten kører |
| `ordhjaelp installer [--autostart]` | Tilføjer til programmenuen (og autostart) |
| `ordhjaelp afinstaller` | Fjerner fra menu og autostart |

Indstillinger (stemme, tempo, genveje): `~/.config/ordhjaelp/config.toml`.
Genvejene kan også ændres i *Systemindstillinger → Tastaturgenveje*.

## Opbygning

```
src/ordhjaelp/
├── services/       logik, uafhængig af styresystem (fx read_aloud.py)
├── tts/            Piper (oplæsning)
├── audio/          afspilning
├── platform/       ALT styresystem-specifikt
│   ├── base.py     interfaces (SelectionProvider, HotkeyProvider)
│   ├── linux/      Wayland/X11, xdg-desktop-portal
│   ├── windows/    (senere)
│   └── macos/      (senere)
├── ipc.py          kommunikation mellem kommandoer og tjenesten
├── daemon.py       baggrundstjenesten
└── cli.py          kommandolinjen
```

Regel: kode uden for `platform/` må ikke kalde styresystemet direkte.

## Udvikling

```bash
uv run pytest          # tests
uv run ruff check .    # kodekvalitet
uv run ruff format .   # formatering
```

## Licens

GPL-3.0-or-later (Piper/espeak-ng er GPL).
