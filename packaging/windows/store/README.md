# Ordhjælp i Microsoft Store

Her ligger det, der skal til for at lægge Ordhjælp i Microsoft Store som en
**MSIX-pakke**. Microsoft signerer MSIX-pakker gratis, så der skal ikke købes et
certifikat (det skal der til den almindelige Setup.exe).

## Det, der er klar

| Fil | Hvad |
|---|---|
| `identitet.toml` | Pakkens navn, udgiver og visningsnavn. **Pladsholdere**, til navnet er reserveret |
| `AppxManifest.xml.in` | Manifestet: mikrofon, `runFullTrust`, start ved login (StartupTask) og kommandoen `ordhjaelp` |
| `make_msix.py` | Udfylder manifestet, laver logoerne og omsætter versionen (Store kræver, at sidste tal er 0) |
| `../build-msix.ps1` | Bygger `dist\Ordhjaelp-<version>.msix` ud fra `dist\Ordhjaelp` |
| `/PRIVATLIV.md` | Privatlivspolitikken, som Store kræver, fordi Ordhjælp bruger mikrofonen |

I programmet:

- Ordhjælp ved, om den kører fra en MSIX-pakke (`platform/windows/store.py`).
- Start ved login bruger pakkens StartupTask i stedet for registreringsdatabasen.
- `ordhjaelp installer` og `afinstaller` siger, at Windows klarer det.
- **Ordforslag er slået fra som standard i Store-udgaven.** Det lytter til alle tastetryk,
  så det skal være elevens eget valg. Fluebenene forklarer, at intet sendes eller gemmes.
- Loggen gemmer ikke længere elevens tekst (diktat, tekst fra skærmen eller under musen).

CI bygger pakken på hver ændring i `packaging/windows/`, signerer en kopi med et
testcertifikat, installerer den, kører `ordhjaelp --help` og tjekker, at
`ordhjaelp afinstaller` ved, at den er pakket.

## Det, du skal gøre

1. **Opret en konto** i [Partner Center](https://partner.microsoft.com/dashboard) som
   privat udvikler (gratis via Microsoft Stores side for udviklere).
2. **Reservér et navn** (Apps og spil → Ny app). Er "Ordhjælp" taget, vælg et andet.
3. **Skriv identiteten ind** i `identitet.toml`. Værdierne står under
   *Produktstyring → Produktidentitet*: `Package/Identity/Name`,
   `Package/Identity/Publisher` og `PublisherDisplayName`. Ret `visningsnavn`, hvis
   navnet er et andet end Ordhjælp.
4. **Byg pakken** (eller hent den fra CI: artefaktet *Ordhjaelp-MSIX*):
   ```powershell
   powershell -File packaging\windows\build-installer.ps1 -SkipInstaller
   powershell -File packaging\windows\build-msix.ps1
   ```
5. **Opret indsendelsen**: upload `.msix`-filen. Udfyld:
   - **Privatlivspolitik:** link til `PRIVATLIV.md` på GitHub.
   - **Aldersvurdering:** spørgeskemaet (ingen køb, ingen chat, intet indhold fra andre).
   - **Skærmbilleder:** knaplinjen, velkomstguiden og indstillingerne.
   - **Begrundelse for `runFullTrust`** og **noter til kontrollanterne**: se nedenfor.

## Begrundelse for runFullTrust (engelsk, til Partner Center)

> Ordhjælp is a desktop application built with Python and Qt (not a UWP app). It needs
> full trust to read selected text (UI Automation), insert dictated text into the active
> application (SendInput), register global hotkeys, show a toolbar on top of other
> windows and run the bundled Tesseract and Hunspell tools.

## Noter til kontrollanterne (engelsk, til Partner Center)

> Ordhjælp is an assistive tool for students with dyslexia and other reading and
> writing difficulties. It reads selected text aloud, transcribes dictation and offers
> word suggestions while typing. Everything runs locally; no data is collected or sent.
>
> **Keyboard observation.** The optional features *word suggestions* and *read while
> typing* use a low-level keyboard hook (WH_KEYBOARD_LL) to see the word currently being
> typed, so suggestions can be shown and words read aloud. Both are **off by default** in
> this version and are turned on by the user in Settings, next to an explanation. Key
> presses are only kept in memory for the current word; nothing is logged or sent.
> Words the user writes are remembered in a local word list to improve suggestions.
>
> **Microphone.** Used only while the user has started dictation. Speech is transcribed
> locally with Whisper (faster-whisper).
>
> **Downloads.** On first start the app downloads language models (voice and speech
> recognition data, not code) from Hugging Face. The user chooses which ones.
>
> **How to test.** Start Ordhjælp, choose "Begge dele" in the welcome guide, and let it
> download the models. Select text in any application and click the blue button (or
> press Ctrl+Alt+L) to hear it read aloud. Click the microphone (Ctrl+Alt+D), speak
> Danish, and click again to insert the text. The interface is in Danish.

## Afprøv pakken på din egen computer

**Nemmest:** Hent artefaktet **Ordhjaelp-MSIX-test** fra en kørsel af
"Windows-installer" i GitHub Actions. Det indeholder en signeret testudgave, dens
testcertifikat og en vejledning (`LAES-MIG.txt`, samme som `LAES-MIG-test.txt` her).
Stol på certifikatet, og dobbeltklik på pakken.

Selv, med Windows SDK (i PowerShell som administrator, fra repoets rod):

```powershell
$udgiver = uv run python packaging\windows\store\make_msix.py --vis udgiver
$cert = New-SelfSignedCertificate -Type Custom -Subject $udgiver -KeyUsage DigitalSignature `
  -CertStoreLocation Cert:\CurrentUser\My -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
Export-Certificate -Cert $cert -FilePath test.cer
Import-Certificate -FilePath test.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
$pfx = Export-PfxCertificate -Cert $cert -FilePath test.pfx -Password (ConvertTo-SecureString test -AsPlainText -Force)
signtool sign /fd SHA256 /f test.pfx /p test dist\Ordhjaelp-<version>.msix
Add-AppxPackage dist\Ordhjaelp-<version>.msix
```

## Ikke afprøvet endnu

- Start ved login gennem StartupTask (WinRT) på en rigtig Windows-computer.
- At diktering beder om lov til mikrofonen og virker inde fra pakken.
- At sprogmodellerne hentes til pakkens egen mappe og slettes ved afinstallation.
- At genstart (når indstillingerne ændres) starter pakken igen korrekt.
