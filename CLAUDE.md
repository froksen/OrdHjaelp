# Ordhjælp: noter til udvikling

Dansk læse og skriveværktøj (LST) i Python og Qt. Kører på Linux (KDE/Wayland først)
og Windows. Alt styresystemspecifikt ligger i `src/ordhjaelp/platform/`.

## Arbejdsgang

- Al tekst i kode, kommentarer, commits og brugerflade er på dansk.
- Hver funktion i sin egen branch ud fra `main`, så den kan blive en selvstændig PR.
- Nye funktioner er slået fra som standard og slås til i indstillingerne.
- **Før push:** kør `scripts/tjek.sh` fra repoet (ikke en kopi andetsteds: scriptet
  skifter til mappen over sin egen placering). Push aldrig, når den fejler.
- **Efter push:** vent på hele CI-resultatet (Linux og Windows), og ret alle fejl i én
  push. Push ikke én rettelse ad gangen.
- Spring aldrig en test over for at få grønt. En test, der tester Linux-kode, må springe
  sig selv over uden for Linux (og omvendt), ikke af andre grunde.

## Kendte faldgruber og løsningerne

### Linux og Windows i samme kode
- **`dbus-fast` findes kun på Linux** (`sys_platform == 'linux'` i `pyproject.toml`).
  Den kan ikke importeres på Windows (`socket.CMSG_LEN` mangler).
  Importér aldrig `ordhjaelp.platform.linux.*` øverst i kode uden for `platform/linux`.
  Brug lazy import inde i `platform/__init__.py`.
- **Testfiler til Linux-kode** skal starte med:
  ```python
  if sys.platform != "linux":
      pytest.skip("kun Linux", allow_module_level=True)
  ```
  `tests/test_platform_imports.py` er en vagt, der fanger det på Linux, før Windows-jobbet
  fejler. Den accepterer `pytest.skip.Exception` (det er sådan, Linux-tests opfører sig på
  Windows).
- **Lad ikke som om, du er Windows** ved at sætte `sys.platform = "win32"`. Så går
  standardbiblioteket i stykker (`_winapi` mangler).
- **ctypes-strukturer:** `wintypes.LONG` er 8 bytes på Linux og 4 på Windows. Test
  størrelser (fx `sizeof(INPUT) == 40`) kun på Windows. Indlæs DLL'er lazy (`functools.cache`),
  så modulerne kan importeres og testes på Linux.

### Windows
- **Registreringsdatabasen:** brug `winreg.CreateKeyEx`, ikke `OpenKey`. `...\Run` findes
  ikke hos en helt ny bruger.
- **Underprocesser** (hunspell, tesseract) skal have
  `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)`, ellers blinker et sort
  konsolvindue, når Ordhjælp kører med `pythonw`.
- **Nedlukning:** `os.kill(pid, SIGTERM)` lukker brat på Windows. Brug
  `signal.raise_signal(signal.SIGTERM)`. `Event.wait()` uden tidsgrænse afbrydes ikke af
  signaler på Windows, så vent i en løkke med `wait(0.5)`.
- **Ctrl+C eller SendInput, mens eleven holder genvejen nede**, bliver til fx Ctrl+Alt+C.
  Kald `win32.wait_for_modifiers_released()` først.
- **Stier:** `platformdirs` giver `%LOCALAPPDATA%\ordhjaelp\ordhjaelp\` på Windows.
- **Tesseract** ligger sjældent i PATH. `find_tesseract()` kigger i Program Files.

### Ordforslag
- Navne med stort (København) kræver programmet **`hunspell`** med dansk ordbog, ikke kun
  ordbogsfilerne. Linux: `hunspell hunspell-da`. Windows CI: MSYS2
  (`mingw-w64-x86_64-hunspell`) og `da_DK.aff/.dic` fra LibreOffice med `DICPATH`.

### D-Bus og AT-SPI (læs under musen)
- Moduler med `dbus_fast.service.ServiceInterface` må **ikke** have
  `from __future__ import annotations`. dbus-fast læser D-Bus-typerne (`"s"`) fra
  annotationerne.
- Genveje fra portalen kaldes i portal-trådens asyncio-løkke. Arbejde, der venter
  (AT-SPI, Ctrl+C), skal i en egen tråd, ellers fejler `asyncio.run`.
- AT-SPI-integrationstesten kræver systemets Python med `gi` (ikke venv'ens), Xvfb,
  xdotool, dbus-launch og at-spi2-core. Kør med `ORDHJAELP_ATSPI_TEST=1`.

### Brugerflade (Qt)
- **Brug aldrig `QLabel.setWordWrap(True)`** i indstillingsvinduet. Qt gætter så vinduets
  bredde ud fra højden og gør det smallere end minimumsbredden. Med en bred skrifttype
  (DejaVu, Noto Sans på KDE) forsvandt "Talegenkendelse:", og tekst blev klippet. Brug
  faste linjeskift (`\n`). `test_no_label_is_clipped` fanger det.
- **Test med en bred skrifttype.** Fejlen sås ikke med Inter, men kun med DejaVu (som
  GitHubs Ubuntu bruger). Kør med en fontconfig, der kun kender DejaVu:
  `FONTCONFIG_FILE=<fil med <dir>…/DejaVuSans.ttf</dir>> QT_QPA_PLATFORM=offscreen ...`
- **Små skærme:** skole-pc'er har ofte 1366x768 med 125 %, altså cirka 614 punkter i
  højden. Indstillingerne ligger derfor i et rulleområde. Afprøv med
  `QT_QPA_PLATFORM="offscreen:configfile=skaerm.json"` med en skærm på 1093x614.
- **Tag skærmbilleder** af vinduer, der ændres, og se på dem. Rendér med
  `widget.render(QImage)` med `setDevicePixelRatio(2)`. Brug ikke `QT_SCALE_FACTOR=2`, for
  det halverer den virtuelle skærm og klemmer vinduet.

### Testmiljø (Linux-container)
- Qt-testene kræver `libegl1 libgl1 libxkbcommon0 libfontconfig1`, og lydtestene
  `libportaudio2`. Kør Qt med `QT_QPA_PLATFORM=offscreen`.

### PR'er og fletning
- PR'er, der rører de samme steder (`config.py`, `ui/settings.py`, README, tests), får
  konflikter efter hinanden. Behold begge sider. Kør `scripts/tjek.sh` efter fletningen.
- Workflowen stopper gamle kørsler ved en ny push (`concurrency`), så en rettet fejl ikke
  meldes igen. En mail om en fejlet kørsel kan derfor være fra en forældet commit:
  tjek commit-id'et.
