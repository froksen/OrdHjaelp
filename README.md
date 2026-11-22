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
- **Enkelt:** en lille knaplinje på skærmen (eller ikoner ved uret), ét klik pr. funktion.
  Indstillinger er gemt væk til voksne

## Funktioner

| | Funktion | Sådan |
|---|---|---|
| 🔊 | **Læs op** | Markér tekst hvor som helst, og klik på den **blå knap** (eller **Ctrl+Alt+L**). Klik igen for at stoppe |
| 🎤 | **Diktering** | Klik i et dokument, klik på den **grønne knap** (eller **Ctrl+Alt+D**), og tal. Klik igen – teksten skrives ind, hvor markøren står |
| ⬚ | **Læs fra skærmen** | Klik på den **lilla knap** (eller **Ctrl+Alt+B**), og træk en firkant om tekst i et billede, en PDF eller et spil |
| ✍️ | **Ordforslag** | Forslag ved markøren, mens der skrives – også ved lydret stavning |
| 🖱️ | **Læs under musen** | Peg med musen og tryk **Ctrl+Alt+1** (ordet), **Ctrl+Alt+2** (sætningen) eller **Ctrl+Alt+3** (herfra og videre). Slås til i indstillingerne |
| 🗣️ | **Læs mens du skriver** | Ordet læses op ved mellemrum og/eller sætningen ved punktum (slås til i indstillingerne) |
| 🖱️ | **Læs ved markering** | Dobbeltklik på et ord, og det læses op. Trippelklik læser linjen eller afsnittet (slås til i indstillingerne) |
| 📄 | **Gør en PDF søgbar** | Klik på den **orange knap**, og vælg en scannet PDF. Der kommer en kopi, hvor teksten kan markeres og læses op. Den gamle PDF bliver ikke ændret |

### Knaplinjen

Knapperne ligger i en lille knaplinje nederst til højre på skærmen, lige over
opgavelinjen. Træk i prikkerne (⠿) for at flytte den, og klik på **‹** for at folde den
ind til en lille fane. Ordhjælp husker, hvor linjen lå. På Wayland huskes pladsen ikke,
og linjen starter altid nederst til højre. Under
**⋯** ligger indstillinger, genveje og Luk. Når knaplinjen bruges, viser Ordhjælp intet
ved uret. Foretrækker man et ikon for hver funktion
ved uret, vælges det i indstillingerne under **Knapper**.

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

### Gør en PDF søgbar

En scannet PDF er bare billeder af sider. Teksten kan ikke markeres, så den kan
ikke læses op. Ordhjælp finder teksten med Tesseract og laver en kopi med et
usynligt tekstlag oven på siderne. Siderne ser ud som før.

- Kopien hedder fx `Opgave (søgbar).pdf` og ligger samme sted som originalen. Originalen ændres ikke
- Sider, der allerede har tekst, kopieres uændret. Kun scannede sider får tekstgenkendelse
- Det tager et par sekunder pr. side. Man kan trykke **Stop** undervejs

### Indstillinger

Klik på **⋯** i knaplinjen (eller højreklik på det blå ikon ved uret, hvis du bruger ikoner)
→ **Indstillinger**. Indstillingerne ligger i fire faner:

| Fane | Indhold |
|---|---|
| **Læs op** | Taletempo (med "Prøv stemmen"), læs ved markering, læs under musen, udklipsholderen |
| **Skriv** | Diktering og talemodel, ordforslag, læs mens du skriver |
| **Knapper** | Knaplinje eller ikoner ved uret, og hvilke knapper der vises |
| **Start og genveje** | Autostart ved login og oversigt over genvejene |

Indstillingerne gemmes i `~/.config/ordhjaelp/config.toml`.

Ordhjælp findes til **Fedora Linux med KDE Plasma** og til **Windows**.

## Installation på Fedora KDE

Hent `ordhjaelp-<version>-1.fc<NN>.x86_64.rpm` under
[Releases](https://github.com/froksen/OrdHjaelp/releases), og installér den:

```bash
sudo dnf install ./ordhjaelp-*.x86_64.rpm
```

RPM'en medbringer sin egen Python 3.13 og alle Python-pakker i `/opt/ordhjaelp`, og den
trækker systemværktøjerne (Tesseract, Hunspell, IBus, wl-clipboard m.fl.) ind via dnf.
Start **Ordhjælp** fra programmenuen.

### Første start

Ved første start åbner et **velkomstvindue**, hvor man vælger, hvilke sprogmodeller der
skal hentes – den danske stemme og den hurtige danske talegenkendelse er valgt på
forhånd (i alt ca. 310 MB). Modellerne hentes **én gang** med statuslinje og virker
derefter uden internet. Flere kan hentes – og ubrugte slettes – under
*Indstillinger → Sprogmodeller …*.

Derefter:

- KDE spørger om lov til **tastaturgenveje**, **tastaturadgang** (til diktering) og
  **skærmbilleder** (til læs fra skærmen) – godkend dem én gang.
- **Ordforslag** kræver, at IBus er valgt som indtastningsmetode:
  *Systemindstillinger → Tastatur → Virtuelt tastatur → **IBus Wayland***.
  Ordhjælp opdager det af sig selv.

## Installation på Windows (prøveudgave)

Der er tre måder. Ingen af dem kræver **administrator**, og begge installerer kun for den
bruger, der er logget ind (i `%LOCALAPPDATA%\Programs\Ordhjaelp`).

**1. Installationsprogrammet:** hent **Ordhjaelp-<version>-Setup.exe** under
[Releases](https://github.com/froksen/OrdHjaelp/releases), og dobbeltklik på den. Der kommer en
genvej i startmenuen, og Ordhjælp kan fjernes under *Indstillinger → Apps*.

**2. PowerShell:** åbn PowerShell, og kopiér denne linje ind:

```powershell
irm https://github.com/froksen/OrdHjaelp/releases/latest/download/install.ps1 | iex
```

Scriptet henter Ordhjælp, lægger en genvej i startmenuen, slår autostart til og starter
Ordhjælp. Ordhjælp kan bagefter fjernes under *Indstillinger → Apps* som andre programmer.
Scriptet kan også hentes og læses igennem først:
[`packaging/windows/install.ps1`](packaging/windows/install.ps1). Valg (fx uden autostart):

```powershell
& ([scriptblock]::Create((irm https://github.com/froksen/OrdHjaelp/releases/latest/download/install.ps1))) -IngenAutostart -Skrivebord
```

**3. winget** (på vej, venter på godkendelse hos Microsoft):

```powershell
winget install OleFrandsen.Ordhjaelp
```

winget bruger det samme installationsprogram og kan også opdatere Ordhjælp
(`winget upgrade OleFrandsen.Ordhjaelp`). Det er praktisk for skolens IT, fordi det kan
køres på mange computere på én gang.

- Hunspell (dansk ordbog) og Tesseract (læs fra skærmen) følger med. Der skal ikke
  installeres andet.
- Første gang hentes stemmen og talegenkendelsen (ca. 300 MB).
- Ordhjælp er ikke signeret endnu. Windows kan derfor vise "Windows beskyttede din pc".
  Klik på **Flere oplysninger** og derefter **Kør alligevel**. Er Smart App Control slået til,
  blokerer Windows installationsprogrammet. Brug så PowerShell-kommandoen.

| Virker på Windows | Sådan |
|---|---|
| Læs op | Den markerede tekst hentes via UI Automation (Windows' tilgængelighed), så udklipsholderen ikke røres. Understøtter programmet ikke det, bruges Ctrl+C, og det, der lå i udklipsholderen, lægges tilbage bagefter. Aldrig Ctrl+C i terminaler |
| Diktering | Teksten skrives ind tegn for tegn, så æ, ø og å virker på alle tastaturer |
| Læs fra skærmen | Tesseract findes også, når det ikke ligger i PATH |
| Genveje og autostart | Genvejene ændres under `[genveje]` i `%LOCALAPPDATA%\ordhjaelp\ordhjaelp\config.toml` |
| Sprogmodeller | Velkomstvinduet henter stemme og talegenkendelse første gang. De kan hentes og slettes under indstillingerne |
| Ordforslag | Forslagene vises i et lille vindue ved markøren. Vælg med F1–F5, med musen eller med ↓ ↑ og Tab. Der skal ikke sættes noget op i Windows |
| Læs mens du skriver | Ordet læses ved mellemrum og sætningen ved punktum, ! og ? |
| Læs ved markering | Træk med musen, dobbeltklik (et ord), trippelklik (en linje) eller Shift+piletaster, så læses det markerede op |
| Læs under musen | Peg og tryk Ctrl+Alt+1 (ordet), Ctrl+Alt+2 (sætningen) eller Ctrl+Alt+3 (herfra). Kræver UI Automation, fx Word, Edge og Notesblok |

Ordforslag virker ikke i programmer, der kører som administrator (det tillader Windows ikke).
Nogle programmer (fx Chrome og Word) fortæller ikke, hvor markøren står. Så vises
forslagene ved musen i stedet.

Bemærk: når Ctrl+C bruges, kan udklipsholderens historik (Win+V) vise den tekst, der er læst op.

## Kommandoer

| Kommando | Hvad den gør |
|---|---|
| `ordhjaelp start` | Starter Ordhjælp med knaplinjen (`--uden-ikon` for kun genveje) |
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
| Tekst fra skærmen og søgbare PDF'er | [Tesseract](https://github.com/tesseract-ocr/tesseract) med den danske sprogpakke | Apache-2.0 |
| Læse og samle PDF'er | [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) med PDFium | Apache-2.0 / BSD-3-Clause |
| Ordforslag – hyppighed | [wordfreq](https://github.com/rspeer/wordfreq) (dansk) | Apache-2.0 (kode) / CC-BY-SA-4.0 (data) |
| Ordforslag – ordbog | Den danske Hunspell-ordbog fra [Stavekontrolden.dk](https://stavekontrolden.dk) | GPL-2.0+ / LGPL-2.1+ / MPL-1.1 |

Modellerne er samlet i et katalog ([`models/catalog.py`](src/ordhjaelp/models/catalog.py))
og hentes af programmet selv – intet er pakket med i repoet eller RPM'en.
Talemodellen kan skiftes i indstillingerne. `ordhjaelp sammenlign-modeller` viser, hvordan
modellerne klarer sig med en rigtig optagelse.

## Opbygning

Ordhjælp er skrevet i **Python** med **Qt (PySide6)** til brugerfladen. Alt, der taler med
styresystemet, ligger bag små interfaces i `platform/`, så resten kan genbruges på
Windows og macOS.

```
src/ordhjaelp/
├── services/       funktionerne: læs op, diktering, læs fra skærmen, ordforslag
├── models/       katalog over sprogmodeller + hent/slet
├── ordmotor/       ordforslag: ordliste, danske lydregler, rangering
├── tts/            oplæsning (Piper)
├── stt/            talegenkendelse (faster-whisper)
├── ocr/            tekstgenkendelse (Tesseract), søgbare PDF'er
├── audio/          afspilning, optagelse, lydsignaler
├── ui/             knaplinje, ikoner ved uret, markering af skærmudsnit, indstillinger (Qt)
├── platform/       ALT styresystem-specifikt
│   ├── base.py     interfaces
│   ├── linux/      Fedora KDE (Wayland): xdg-desktop-portal, KWin, IBus, wl-clipboard
│   ├── windows/    Win32 via ctypes: genveje, UI Automation, SendInput, tastaturovervågning
│   └── macos/      (senere)
├── ipc.py          lokal forbindelse mellem kommandoer, IBus og tjenesten
├── daemon.py       baggrundstjenesten
└── cli.py          kommandolinjen
```

På Linux/Wayland bruger Ordhjælp **xdg-desktop-portal** til genveje (GlobalShortcuts),
indsættelse af dikteret tekst (RemoteDesktop) og skærmbilleder (Screenshot), og **IBus**
til ordforslag. IBus-delen er en tynd klient, der kører med systemets Python og henter
forslagene fra Ordhjælp-tjenesten.

På Windows lytter Ordhjælp efter tastetryk med en tastaturovervågning (`WH_KEYBOARD_LL`).
Bogstaverne går direkte til programmet. Vælges et forslag, slettes det skrevne ord med
Backspace, og forslaget skrives i stedet. Kun tasterne til at vælge forslag holdes tilbage,
og kun mens forslagene vises. Logikken ligger i `platform/windows/typing_tracker.py` og
testes på alle systemer.

## Udvikling

Kør fra kildekoden på Fedora KDE:

```bash
sudo dnf install wl-clipboard portaudio tesseract tesseract-langpack-dan hunspell-da ibus at-spi2-core xdotool
pip install --user uv
git clone https://github.com/froksen/OrdHjaelp.git ordhjaelp && cd ordhjaelp
uv sync
uv run ordhjaelp installer --autostart   # menupunkt + start ved login
uv run ordhjaelp start
```

Eller på Windows:

```powershell
winget install astral-sh.uv
winget install UB-Mannheim.TesseractOCR   # til "læs fra skærmen" (vælg den danske sprogpakke)
git clone https://github.com/froksen/OrdHjaelp.git ordhjaelp; cd ordhjaelp
uv sync
uv run ordhjaelp installer --autostart    # start ved login
uv run ordhjaelp start
```

Tests og kontrol:

```bash
scripts/tjek.sh                   # alt det, GitHub Actions kører på Linux (før push)
uv run pytest                     # tests
uv run ruff check . && uv run ruff format .
ORDHJAELP_IBUS_TEST=1 uv run pytest tests/integration   # IBus-test med privat ibus-daemon
ORDHJAELP_ATSPI_TEST=1 uv run pytest tests/integration/test_atspi.py   # læs under musen (Xvfb + AT-SPI)
```

**Windows-installationsprogrammet** og zip-filen, som PowerShell-kommandoen henter, bygges af
GitHub Actions ved en tag (`v0.3.0`) og lægges på udgivelsen. **RPM'en** bygges også af
GitHub Actions i en Fedora-container, der afprøver, at den kan installeres med dnf. Lokalt:
`packaging/linux/build-rpm.sh` (kræver `rpm-build`).

Windows lokalt (kræver Inno Setup 6, og MSYS2 for at få Hunspell og Tesseract med):

```powershell
powershell -File packaging\windows\build-installer.ps1                            # Setup.exe og zip-filen i dist\
powershell -File packaging\windows\build-installer.ps1 -SkipInstaller -NoTools   # kun dist\Ordhjaelp\
```

**Hjælp med ordforslag:** Den bedste måde at gøre ordforslagene bedre på er rigtige
stavefejl fra elever. Tilføj dem til [`tests/ordmotor/fejlkorpus.tsv`](tests/ordmotor/fejlkorpus.tsv)
(det skrevne, tabulator, det rigtige ord) – testen viser, hvilke der ikke bliver fanget.

## Status

Ordhjælp er under udvikling og afprøves på Fedora KDE Plasma (Wayland).

- [x] Læs op, diktering, læs fra skærmen
- [x] Ordforslag med fonetisk matching, læs mens du skriver
- [x] Indstillinger, autostart, RPM
- [x] Velkomstvindue ved første start: vælg og hent sprogmodeller; administrér dem i indstillingerne
- [x] Windows: læs op, diktering, læs fra skærmen, genveje, autostart (prøveudgave)
- [x] Windows: sprogmodeller, ordforslag, læs mens du skriver (prøveudgave)
- [x] Windows: installer uden administrator (prøveudgave)
- [x] Windows: læs ved markering, læs under musen (UI Automation, prøveudgave)
- [ ] Windows: signeret installer
- [ ] macOS

## Forfattere

- **Ole Frandsen** ([@froksen](https://github.com/froksen)): hovedforfatter og vedligeholder
- **qvisty** ([@qvisty](https://github.com/qvisty)): bidragsyder (Windows-udgaven, læs ved
  markering, læs under musen, udviklingsnoter)

I programmet viser **Om Ordhjælp …** i menuen forfatterne og alle de frie projekter,
Ordhjælp bygger på (listen ligger i [`ui/about.py`](src/ordhjaelp/ui/about.py)).

## Kodesignering (code signing policy)

Ordhjælp er søgt om gratis kodesignering hos [SignPath Foundation](https://signpath.org/).
Indtil det er godkendt, er Windows-filerne **ikke** signeret.

Alle filer til Windows bygges af GitHub Actions direkte fra kildekoden i dette repo
([`.github/workflows/windows-installer.yml`](.github/workflows/windows-installer.yml)).
Ingen bygger dem på sin egen computer.

**Roller:**

| Rolle | Hvem |
|---|---|
| Forfattere (committers) | [Ole Frandsen (@froksen)](https://github.com/froksen) |
| Gennemlæsere (reviewers) | [Ole Frandsen (@froksen)](https://github.com/froksen) |
| Godkendere (approvers) | [Ole Frandsen (@froksen)](https://github.com/froksen) |
| Bidragsydere | [qvisty (@qvisty)](https://github.com/qvisty) og andre, der laver pull requests |

- Alle ændringer fra bidragsydere kommer ind som pull requests og gennemlæses af en
  forfatter, før de flettes. Det gælder også byggescripts og GitHub Actions.
- Hver udgivelse, der skal signeres, godkendes manuelt af en godkender.
- Alle i teamet bruger to-trinslogin (MFA) på GitHub.

<!-- Når SignPath har godkendt projektet, erstattes de to første linjer i afsnittet med:
Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org)
-->

### Privatliv

Ordhjælp kører på computeren og sender ingen tekst, lyd eller oplysninger om brugeren ud.
Programmet henter kun noget fra internettet, når brugeren beder om det eller første gang:

- sprogmodeller (stemme og talegenkendelse) fra [Hugging Face](https://huggingface.co)
- ved installation med PowerShell: den nyeste udgave fra GitHub (`api.github.com` og `github.com`)

Der er ingen statistik, sporing eller automatisk opdatering. Indstillinger og sprogmodeller
ligger kun på computeren (`%LOCALAPPDATA%\ordhjaelp` på Windows, `~/.config/ordhjaelp` og
`~/.local/share/ordhjaelp` på Linux).

## Licens

[GPL-3.0-or-later](LICENSE).
