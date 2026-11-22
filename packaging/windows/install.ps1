# Installer Ordhjaelp paa Windows uden administrator: hent zip-filen fra den nyeste
# udgivelse, pak den ud i %LOCALAPPDATA%\Programs\Ordhjaelp, og laeg en genvej i
# startmenuen. Hunspell og Tesseract foelger med i zip-filen.
#
# Installer (i PowerShell):
#   irm https://github.com/froksen/OrdHjaelp/releases/latest/download/install.ps1 | iex
# Med valg:
#   & ([scriptblock]::Create((irm https://github.com/froksen/OrdHjaelp/releases/latest/download/install.ps1))) -IngenAutostart
# Afinstaller:
#   & "$env:LOCALAPPDATA\Programs\Ordhjaelp\install.ps1" -Afinstaller
#
# Filen er bevidst kun ASCII: PowerShell 5.1 laeser et script fra nettet med et andet
# tegnsaet, saa ae, oe og aa laves af tegnkoder herunder.
param(
    [switch]$Afinstaller,
    [switch]$IngenAutostart,    # start ikke Ordhjaelp automatisk ved login
    [switch]$IngenGenvej,       # ingen genvej i startmenuen
    [switch]$Skrivebord,        # ogsaa en genvej paa skrivebordet
    [switch]$IkkeStart,         # start ikke Ordhjaelp efter installationen
    [string]$Zip = "",          # brug en zip-fil, der allerede er hentet (fx uden internet)
    [string]$Version = "latest",
    [string]$Mappe = "$env:LOCALAPPDATA\Programs\Ordhjaelp"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # ellers er Invoke-WebRequest meget langsom i PowerShell 5.1

$ae = [char]0xE6; $oe = [char]0xF8; $aa = [char]0xE5
$Navn = "Ordhj${ae}lp"
$Repo = "froksen/OrdHjaelp"
$Exe = Join-Path $Mappe "Ordhjaelp.exe"
$Startmenu = Join-Path ([Environment]::GetFolderPath("Programs")) "$Navn.lnk"
$SkrivebordGenvej = Join-Path ([Environment]::GetFolderPath("Desktop")) "$Navn.lnk"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Ordhjaelp"

function Skriv([string]$tekst) { Write-Host "  $tekst" }

function Luk-Ordhjaelp {
    # Luk paent via Ordhjaelp selv, ellers hjaelper Windows til
    if (Test-Path $Exe) {
        Start-Process $Exe -ArgumentList "afslut" -Wait -ErrorAction SilentlyContinue | Out-Null
    }
    for ($i = 0; $i -lt 20; $i++) {
        $proc = Get-Process -Name Ordhjaelp -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -and $_.Path.StartsWith($Mappe, [StringComparison]::OrdinalIgnoreCase) }
        if (-not $proc) { return }
        Start-Sleep -Milliseconds 250
    }
    $proc | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

function Ny-Genvej([string]$sti) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($sti)
    $link.TargetPath = $Exe
    $link.WorkingDirectory = $Mappe
    $link.Description = "Dansk l${ae}se- og skrivehj${ae}lp"
    $link.Save()
}

# -- afinstaller -------------------------------------------------------------------
function Afinstaller-Ordhjaelp {
    Write-Host "Afinstallerer $Navn ..."
    if (Test-Path $Exe) {
        Start-Process $Exe -ArgumentList "afinstaller" -Wait -ErrorAction SilentlyContinue | Out-Null
    }
    Luk-Ordhjaelp
    foreach ($genvej in $Startmenu, $SkrivebordGenvej) {
        if (Test-Path $genvej) { Remove-Item $genvej -Force }
    }
    if (Test-Path $UninstallKey) { Remove-Item $UninstallKey -Recurse -Force }
    if (Test-Path $Mappe) { Remove-Item $Mappe -Recurse -Force }
    Skriv "$Navn er fjernet."
    Skriv "Indstillinger og sprogmodeller ligger stadig i $env:LOCALAPPDATA\ordhjaelp"
    Skriv "og kan slettes, hvis de ikke skal bruges igen."
}

# -- installer ---------------------------------------------------------------------
function Installer-Ordhjaelp {
    Write-Host "Installerer $Navn ..."
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("ordhjaelp-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        $scriptKilde = $null
        if ($Zip) {
            $zipFil = (Resolve-Path $Zip).Path
            Skriv "Bruger $zipFil"
        } else {
            # GitHub kraever TLS 1.2, som PowerShell 5.1 ikke altid bruger af sig selv
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
            $api = if ($Version -eq "latest") { "https://api.github.com/repos/$Repo/releases/latest" }
                   else { "https://api.github.com/repos/$Repo/releases/tags/$Version" }
            $udgivelse = Invoke-RestMethod -Uri $api -UseBasicParsing -Headers @{ "User-Agent" = "Ordhjaelp-install" }
            $aktiv = $udgivelse.assets | Where-Object { $_.name -like "*-Windows.zip" } | Select-Object -First 1
            if (-not $aktiv) { throw "Udgivelsen $($udgivelse.tag_name) har ingen zip-fil til Windows." }
            $mb = [math]::Round($aktiv.size / 1MB)
            Skriv "Henter $($aktiv.name) ($mb MB) ..."
            $zipFil = Join-Path $tmp $aktiv.name
            Invoke-WebRequest -Uri $aktiv.browser_download_url -OutFile $zipFil -UseBasicParsing
            $scriptKilde = $udgivelse.assets | Where-Object { $_.name -eq "install.ps1" } | Select-Object -First 1
        }

        Skriv "Pakker ud ..."
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $udpakket = Join-Path $tmp "udpakket"
        [IO.Compression.ZipFile]::ExtractToDirectory($zipFil, $udpakket)
        $ny = Join-Path $udpakket "Ordhjaelp"
        if (-not (Test-Path (Join-Path $ny "Ordhjaelp.exe"))) { throw "Zip-filen indeholder ikke Ordhjaelp\Ordhjaelp.exe." }

        # En tidligere installation med installeren (Setup.exe) ligger i samme mappe
        $gammelInstaller = Join-Path $Mappe "unins000.exe"
        if (Test-Path $gammelInstaller) {
            Skriv "Fjerner den udgave, der er installeret med Setup.exe ..."
            Luk-Ordhjaelp
            try { Start-Process $gammelInstaller -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES" -Wait } catch {
                throw "Kunne ikke fjerne den gamle udgave. Afinstaller den under Indstillinger -> Apps, og proev igen."
            }
        }

        Luk-Ordhjaelp
        if (Test-Path $Mappe) { Remove-Item $Mappe -Recurse -Force }
        New-Item -ItemType Directory -Path (Split-Path $Mappe) -Force | Out-Null
        Move-Item $ny $Mappe

        # Gem scriptet i programmappen, saa det kan afinstallere igen
        $mitScript = Join-Path $Mappe "install.ps1"
        if ($PSCommandPath) {
            Copy-Item $PSCommandPath $mitScript -Force
        } elseif ($scriptKilde) {
            Invoke-WebRequest -Uri $scriptKilde.browser_download_url -OutFile $mitScript -UseBasicParsing
        }

        if (-not $IngenGenvej) { Ny-Genvej $Startmenu; Skriv "Genvej i startmenuen: $Navn" }
        if ($Skrivebord) { Ny-Genvej $SkrivebordGenvej; Skriv "Genvej p${aa} skrivebordet" }

        # Vises under Indstillinger -> Apps, saa Ordhjaelp kan fjernes som andre programmer
        if (Test-Path $mitScript) {
            New-Item -Path $UninstallKey -Force | Out-Null
            $afinstaller = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$mitScript`" -Afinstaller -Mappe `"$Mappe`""
            $produktVersion = (Get-Item $Exe).VersionInfo.ProductVersion
            $vaerdier = @{
                DisplayName = $Navn; DisplayIcon = $Exe; Publisher = "Ole Frandsen"
                DisplayVersion = $produktVersion; InstallLocation = $Mappe; UninstallString = $afinstaller
                URLInfoAbout = "https://github.com/$Repo"
            }
            foreach ($k in $vaerdier.Keys) { Set-ItemProperty -Path $UninstallKey -Name $k -Value $vaerdier[$k] }
            foreach ($k in "NoModify", "NoRepair") {
                New-ItemProperty -Path $UninstallKey -Name $k -Value 1 -PropertyType DWord -Force | Out-Null
            }
        }

        # Autostart med Ordhjaelps egen indstilling, saa fluebenet i indstillingerne passer
        $valg = if ($IngenAutostart) { @("afinstaller") } else { @("installer", "--autostart") }
        Start-Process $Exe -ArgumentList $valg -Wait | Out-Null
        if (-not $IngenAutostart) { Skriv "Starter automatisk, n${aa}r du logger ind" }

        Skriv "$Navn er installeret i $Mappe"
        if (-not $IkkeStart) {
            Start-Process $Exe -ArgumentList "start"
            Skriv "$Navn starter nu. F${oe}rste gang hentes stemme og talegenkendelse (ca. 300 MB)."
        }
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
}

if ($Afinstaller) { Afinstaller-Ordhjaelp } else { Installer-Ordhjaelp }
