# Ordhjælp

Dansk læse- og skrivehjælp (LST) til Linux – gratis, open source og offline.
Senere også Windows og macOS.

**Sådan bruges den:** Markér tekst hvor som helst, og **klik på det blå ikon ved uret**
(eller tryk **Ctrl+Alt+L**). Teksten læses op med en naturlig dansk stemme.
Mens der læses, er ikonet rødt – klik igen (eller **Ctrl+Alt+S**) for at stoppe.

**Diktering:** Klik i et dokument, klik på det **grønne mikrofonikon** (eller **Ctrl+Alt+D**)
og tal. Klik igen, når du er færdig – teksten skrives ind, hvor markøren står.
Første gang spørger KDE, om Ordhjælp må bruge tastaturet.

**Ordforslag:** Mens der skrives, vises forslag ved markøren – også ved lydret stavning
("sgole" → *skole*). **↓/↑** vælger (ordet læses op), **Tab** eller **mellemrum** tager det
valgte, **F1–F5** eller klik vælger direkte, og **højreklik** læser et forslag op. Uden valg bliver det skrevne stående.
Kræver IBus: *Systemindstillinger → Tastatur → Virtuelt tastatur → IBus Wayland*.
Ord, eleven bruger, huskes lokalt (`~/.local/share/ordhjaelp/egne_ord.json`).

**Læs fra skærmen:** Klik på det **lilla ikon** (eller **Ctrl+Alt+B**), og træk en firkant om
tekst i et billede, en PDF eller et spil. Teksten læses op. Esc fortryder.

## Kom i gang (Fedora/KDE)

```bash
sudo dnf install wl-clipboard portaudio \
    tesseract tesseract-langpack-dan         # markeret tekst, lyd, tekstgenkendelse
pip install --user uv                        # projektværktøj
cd ~/Udvikling/LST
uv sync                                      # installerer afhængigheder
uv run ordhjaelp installer --autostart       # menu + start ved login
uv run ordhjaelp start                       # første gang: godkend genvejene i KDE-dialogen
```

Stemmen (ca. 60 MB) og talegenkendelsen (ca. 250 MB) hentes automatisk første gang.

## Kommandoer

| Kommando | Hvad den gør |
|---|---|
| `ordhjaelp start` | Starter tjenesten med ikon ved uret (`--uden-ikon` for uden) |
| `ordhjaelp afslut` | Lukker Ordhjælp helt |
| `ordhjaelp laes` | Læser markeret tekst op – eller stopper, hvis der læses |
| `ordhjaelp stop` | Stopper oplæsning |
| `ordhjaelp dikter` | Starter/stopper diktering |
| `ordhjaelp skaerm` | Læs tekst fra et udsnit af skærmen |
| `ordhjaelp sammenlign-modeller` | Optag en sætning og se, hvad hver talemodel hører |
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
├── ordmotor/       ordforslag: ordliste (wordfreq + Hunspell), lydregler, rangering
├── ocr/            Tesseract (tekst fra skærmen)
├── stt/            Whisper (diktering) – kun færdige modeller fra Hugging Face
├── audio/          afspilning
├── platform/       ALT styresystem-specifikt
│   ├── base.py     interfaces (SelectionProvider, HotkeyProvider)
│   ├── linux/      Wayland/X11, xdg-desktop-portal
│   ├── windows/    (senere)
│   └── macos/      (senere)
├── ui/             ikon ved uret (Qt – virker på alle styresystemer)
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
ORDHJAELP_IBUS_TEST=1 uv run pytest tests/integration   # IBus-test (privat ibus-daemon)
```

## Licens

GPL-3.0-or-later (Piper/espeak-ng er GPL).
