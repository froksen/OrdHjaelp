# Ordhjælp

> **In English:** Ordhjælp ("word help") is a free, open-source reading and writing aid
> for Danish pupils with dyslexia or reading/writing difficulties – an alternative to
> commercial tools such as AppWriter and IntoWords, built for Linux (KDE/Wayland first,
> with Windows and macOS in mind). It reads selected text aloud with a natural Danish
> voice, turns speech into text, reads text from any part of the screen (OCR), and offers
> word suggestions while typing – including for phonetic misspellings such as
> *"sgole" → "skole"*. Everything runs offline on the computer, using only ready-made,
> openly licensed models and word lists. It is designed to be simple enough for children
> to use with one click.

---

Ordhjælp er et gratis læse- og skriveværktøj (LST) til danske elever. Det er lavet som et
alternativ til AppWriter og IntoWords på **Linux** og er bygget, så det senere kan flyttes
til Windows og macOS.

- **Gratis og open source** (GPL-3.0)
- **Offline:** stemme, talegenkendelse og ordforslag kører på computeren – intet sendes ud
- **Enkelt:** tre ikoner ved uret, ét klik pr. funktion. Indstillinger er gemt væk til voksne

## Funktioner

| | Funktion | Sådan |
|---|---|---|
| 🔊 | **Læs op** | Markér tekst hvor som helst, og klik på det **blå ikon** (eller **Ctrl+Alt+L**). Klik igen for at stoppe |
| 🎤 | **Diktering** | Klik i et dokument, klik på det **grønne ikon** (eller **Ctrl+Alt+D**), og tal. Klik igen – teksten skrives ind, hvor markøren står |
| ⬚ | **Læs fra skærmen** | Klik på det **lilla ikon** (eller **Ctrl+Alt+B**), og træk en firkant om tekst i et billede, en PDF eller et spil |
| ✍️ | **Ordforslag** | Forslag ved markøren, mens der skrives – også ved lydret stavning |
| 🖱️ | **Læs under musen** | Peg med musen og tryk **Ctrl+Alt+1** (ordet), **Ctrl+Alt+2** (sætningen) eller **Ctrl+Alt+3** (herfra og videre). Slås til i indstillingerne |
| 🗣️ | **Læs mens du skriver** | Ordet læses op ved mellemrum og/eller sætningen ved punktum (slås til i indstillingerne) |

### Ordforslag

Ordforslag forstår typiske fejl hos yngre elever og ordblinde:

| Eleven skriver | Forslag |
|---|---|
| sgole | **skole** |
| vordan | **hvordan** |
| fotbol | **fodbold** |
| pluseli | **pludselig** |
| løda | **lørdag** |
| Køben | **København** |

- **↓ / ↑** vælger et forslag – det valgte **læses op**
- **Tab** eller **mellemrum** tager det valgte forslag. **F1–F5** eller klik vælger direkte
- **Højreklik** på et forslag læser det op uden at vælge det
- Uden valg bliver det skrevne stående – forslagene ændrer aldrig noget af sig selv
- Ord, eleven bruger, huskes lokalt og foreslås oftere (også nye ord som navne)

Ordmotoren kombinerer tre ting: begyndelsen af ordet, en **dansk lydnøgle** (stumme
bogstaver som i *hvad/hjem/mand/dejlig*, *sg/sk*, *æ/e*, endelser m.m.) og stavelighed.
Den testes mod en samling typiske stavefejl
([`tests/ordmotor/fejlkorpus.tsv`](tests/ordmotor/fejlkorpus.tsv)).

### Læs under musen

Ordhjælp spørger programmet, hvilken tekst der står under musen. Det bruger
tilgængeligheds-API'en **AT-SPI**, den samme som skærmlæseren Orca.

- Virker i programmer med god tilgængelighed: Firefox, LibreOffice, Kate, KDE- og GTK-programmer
- Chrome og Electron-programmer skal måske startes med `--force-renderer-accessibility`
- Virker ikke i billeder, scannede PDF'er og spil. Brug **Læs fra skærmen** dér
- På Wayland kræver det **KDE Plasma**: KWin fortæller, hvor musen er. På X11 bruges `xdotool`
- Genvejene registreres ved start, så Ordhjælp genstarter, når funktionen slås til eller fra

### Indstillinger

Højreklik på det blå ikon → **Indstillinger**: taletempo (med "Prøv stemmen"),
diktering og talemodel, ordforslag, læs mens du skriver, hvilke ikoner der vises, og
autostart ved login. Indstillingerne gemmes i `~/.config/ordhjaelp/config.toml`.

## Installation (Fedora KDE)

### Med RPM

Byg RPM'en (kræver `rpm-build`):

```bash
sudo dnf install rpm-build
packaging/linux/build-rpm.sh          # → build/rpm/ordhjaelp-<version>.x86_64.rpm
```

Installér den på maskinen, der skal bruge Ordhjælp:

```bash
sudo dnf install ./ordhjaelp-*.x86_64.rpm
```

RPM'en medbringer sin egen Python 3.13 og alle Python-pakker i `/opt/ordhjaelp`, og den
trækker systemværktøjerne (Tesseract, Hunspell, IBus, wl-clipboard m.fl.) ind via dnf.
Start **Ordhjælp** fra programmenuen.

### Fra kildekoden

```bash
sudo dnf install wl-clipboard portaudio tesseract tesseract-langpack-dan hunspell-da ibus at-spi2-core xdotool
pip install --user uv
git clone https://github.com/froksen/OrdHj-lp.git ordhjaelp && cd ordhjaelp
uv sync
uv run ordhjaelp installer --autostart   # menupunkt + start ved login
uv run ordhjaelp start
```

### Første start

- **Kræver internet:** den danske stemme (ca. 60 MB) og talegenkendelsen (ca. 250 MB)
  hentes første gang, og ordlisten bygges. Derefter kører alt offline.
- KDE spørger om lov til **tastaturgenveje**, **tastaturadgang** (til diktering) og
  **skærmbilleder** (til læs fra skærmen) – godkend dem én gang.
- **Ordforslag** kræver, at IBus er valgt som indtastningsmetode:
  *Systemindstillinger → Tastatur → Virtuelt tastatur → **IBus Wayland***.
  Ordhjælp opdager det af sig selv.

## Installation (Windows, prøveudgave)

Windows-udgaven er ny og endnu ikke afprøvet bredt. Der er ingen installer endnu.

```powershell
winget install astral-sh.uv
winget install UB-Mannheim.TesseractOCR   # til "læs fra skærmen" (vælg den danske sprogpakke)
git clone https://github.com/froksen/OrdHj-lp.git ordhjaelp; cd ordhjaelp
uv sync
uv run ordhjaelp installer --autostart    # start ved login
uv run ordhjaelp start
```

| Virker på Windows | Sådan |
|---|---|
| Læs op | Markeret tekst kopieres med Ctrl+C, og det, der lå i udklipsholderen, lægges tilbage bagefter |
| Diktering | Teksten skrives ind tegn for tegn, så æ, ø og å virker på alle tastaturer |
| Læs fra skærmen | Tesseract findes også, når det ikke ligger i PATH |
| Genveje og autostart | Genvejene ændres under `[genveje]` i `%LOCALAPPDATA%\ordhjaelp\ordhjaelp\config.toml` |

Kommer senere på Windows: ordforslag, læs ved markering og læs under musen.
Bemærk: udklipsholderens historik (Win+V) kan vise den tekst, der er læst op.

## Kommandoer

| Kommando | Hvad den gør |
|---|---|
| `ordhjaelp start` | Starter Ordhjælp med ikoner ved uret (`--uden-ikon` for uden) |
| `ordhjaelp afslut` | Lukker Ordhjælp |
| `ordhjaelp laes` / `stop` | Læser markeret tekst op / stopper |
| `ordhjaelp sig "tekst"` | Læser en tekst op |
| `ordhjaelp dikter` | Starter/stopper diktering |
| `ordhjaelp skaerm` | Læs tekst fra et udsnit af skærmen |
| `ordhjaelp laes-ord` / `laes-saetning` / `laes-herfra` | Læs ordet, sætningen eller herfra under musen |
| `ordhjaelp sammenlign-modeller` | Optag en sætning og se, hvad hver talemodel hører – godt til at vælge model ud fra elevens egen stemme |
| `ordhjaelp status` | Viser om Ordhjælp kører |
| `ordhjaelp installer [--autostart]` / `afinstaller` | Menupunkt og autostart for brugeren |

## Modeller og data

Ordhjælp bruger kun **færdige modeller og ordlister, som andre vedligeholder** – der
trænes eller konverteres ikke egne modeller. Vedligeholdet ligger på selve programmet.

| Til | Kilde | Licens |
|---|---|---|
| Oplæsning | [Piper](https://github.com/OHF-Voice/piper1-gpl) med stemmen `da_DK-talesyntese-medium` | GPL-3.0 (Piper) / CC0 (stemmens træningsdata) |
| Diktering (standard) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT) med [`lucasw89/whisper-small-danish-ct2-int8`](https://huggingface.co/lucasw89/whisper-small-danish-ct2-int8) (dansk udgave af Whisper small) | MIT |
| Diktering (valgfrit) | [`q-henric/whisper-large-v3-turbo-danish-ct2`](https://huggingface.co/q-henric/whisper-large-v3-turbo-danish-ct2), CoRal [røst-v3](https://huggingface.co/pluttodk/roest-v3-whisper-1.5b-ct2), OpenAI Whisper small/turbo | MIT / OpenRAIL |
| Tekst fra skærmen | [Tesseract](https://github.com/tesseract-ocr/tesseract) med den danske sprogpakke | Apache-2.0 |
| Ordforslag – hyppighed | [wordfreq](https://github.com/rspeer/wordfreq) (dansk) | Apache-2.0 (kode) / CC-BY-SA-4.0 (data) |
| Ordforslag – ordbog | Den danske Hunspell-ordbog fra [Stavekontrolden.dk](https://stavekontrolden.dk) | GPL-2.0+ / LGPL-2.1+ / MPL-1.1 |

Talemodellen kan skiftes i indstillingerne. `ordhjaelp sammenlign-modeller` viser, hvordan
modellerne klarer sig med en rigtig optagelse.

## Opbygning

Ordhjælp er skrevet i **Python** med **Qt (PySide6)** til brugerfladen. Alt, der taler med
styresystemet, ligger bag små interfaces i `platform/`, så resten kan genbruges på
Windows og macOS.

```
src/ordhjaelp/
├── services/       funktionerne: læs op, diktering, læs fra skærmen, ordforslag
├── ordmotor/       ordforslag: ordliste, danske lydregler, rangering
├── tts/            oplæsning (Piper)
├── stt/            talegenkendelse (faster-whisper)
├── ocr/            tekstgenkendelse (Tesseract)
├── audio/          afspilning, optagelse, lydsignaler
├── ui/             ikoner ved uret, markering af skærmudsnit, indstillinger (Qt)
├── platform/       ALT styresystem-specifikt
│   ├── base.py     interfaces
│   ├── linux/      Wayland/X11: xdg-desktop-portal, IBus, wl-clipboard
│   ├── windows/    (senere)
│   └── macos/      (senere)
├── ipc.py          lokal forbindelse mellem kommandoer, IBus og tjenesten
├── daemon.py       baggrundstjenesten
└── cli.py          kommandolinjen
```

På Linux/Wayland bruger Ordhjælp **xdg-desktop-portal** til genveje (GlobalShortcuts),
indsættelse af dikteret tekst (RemoteDesktop) og skærmbilleder (Screenshot), og **IBus**
til ordforslag. IBus-delen er en tynd klient, der kører med systemets Python og henter
forslagene fra Ordhjælp-tjenesten.

## Udvikling

```bash
uv run pytest                     # tests
uv run ruff check . && uv run ruff format .
ORDHJAELP_IBUS_TEST=1 uv run pytest tests/integration   # IBus-test med privat ibus-daemon
ORDHJAELP_ATSPI_TEST=1 uv run pytest tests/integration/test_atspi.py   # læs under musen (Xvfb + AT-SPI)
```

**Hjælp med ordforslag:** Den bedste måde at gøre ordforslagene bedre på er rigtige
stavefejl fra elever. Tilføj dem til [`tests/ordmotor/fejlkorpus.tsv`](tests/ordmotor/fejlkorpus.tsv)
(det skrevne, tabulator, det rigtige ord) – testen viser, hvilke der ikke bliver fanget.

## Status

Ordhjælp er under udvikling og afprøves på Fedora KDE Plasma (Wayland).

- [x] Læs op, diktering, læs fra skærmen
- [x] Ordforslag med fonetisk matching, læs mens du skriver
- [x] Indstillinger, autostart, RPM
- [ ] Synlig besked ved første start, mens modellerne hentes
- [x] Windows: læs op, diktering, læs fra skærmen, genveje, autostart (prøveudgave)
- [ ] Windows: ordforslag, læs ved markering, læs under musen, installer
- [ ] macOS

## Licens

[GPL-3.0-or-later](LICENSE).
