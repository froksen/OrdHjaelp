# Ordhjælp i winget

Manifesterne her beskriver Ordhjælp for **winget** (Windows' egen pakkehåndtering). Når
pakken er godkendt i [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs), kan
Ordhjælp installeres og opdateres med:

```powershell
winget install OleFrandsen.Ordhjaelp
winget upgrade OleFrandsen.Ordhjaelp
```

winget bruger det samme `Setup.exe` som på udgivelsen og installerer for den bruger, der er
logget ind (uden administrator).

## Første indsendelse (én gang, i hånden)

Kopiér de fire `.yaml`-filer til `manifests/o/OleFrandsen/Ordhjaelp/<version>/` i en fork af
winget-pkgs, og lav en pull request. Eller på Windows:

```powershell
winget validate packaging\windows\winget
winget install --manifest packaging\windows\winget     # afprøv (kræver LocalManifestFiles slået til)
wingetcreate submit packaging\windows\winget --token <token>
```

## Nye versioner (automatisk)

Når en tag som `v0.5.0` bygges, opdaterer `windows-installer.yml` pakken i winget med
`wingetcreate update` og laver selv pull requesten til winget-pkgs. Det sker kun, når:

- pakken allerede findes i winget-pkgs (efter den første indsendelse), og
- repoet har hemmeligheden `WINGET_TOKEN`: en *classic* GitHub-token med `public_repo`.

Filerne her opdateres ikke af sig selv. Versionen i dem er den, der først blev sendt ind.
