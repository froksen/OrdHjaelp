# Hent Hunspell og Tesseract med dansk ordbog og sprogmodel til Windows-installeren.
#
# Programmerne hentes fra MSYS2 (findes på GitHubs Windows-maskiner i C:\msys64).
# Hver .exe kopieres med de DLL'er, den bruger, til packaging\windows\build\tools\.
# Brug: powershell -File packaging\windows\fetch-tools.ps1 [-Msys C:\msys64]
param([string]$Msys = "C:\msys64")

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$tools = Join-Path $here "build\tools"
$bin = Join-Path $Msys "mingw64\bin"
$pacman = Join-Path $Msys "usr\bin\pacman.exe"
if (-not (Test-Path $pacman)) { throw "MSYS2 findes ikke i $Msys" }

# Dansk ordbog fra LibreOffice og den hurtige danske sprogmodel til Tesseract
$dictUrl = "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/da_DK"
$tessdataUrl = "https://github.com/tesseract-ocr/tessdata_fast/raw/4.1.0"

Write-Host "== MSYS2-pakker"
& $pacman -Sy --noconfirm --needed `
  mingw-w64-x86_64-hunspell mingw-w64-x86_64-tesseract-ocr mingw-w64-x86_64-ntldd
if ($LASTEXITCODE) { throw "pacman fejlede" }

function Copy-WithDlls([string]$exe, [string]$dest) {
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  Copy-Item (Join-Path $bin $exe) $dest
  # ntldd -R: alle DLL'er, programmet bruger (også indirekte). Kun dem fra MSYS2 kopieres;
  # Windows' egne (kernel32.dll osv.) findes på alle computere.
  $deps = & (Join-Path $bin "ntldd.exe") -R (Join-Path $bin $exe)
  foreach ($line in $deps) {
    if ($line -match "=>\s+(\S+\\mingw64\\bin\\\S+\.dll)") {
      Copy-Item $Matches[1] $dest -Force
    }
  }
}

if (Test-Path $tools) { Remove-Item -Recurse -Force $tools }

Write-Host "== Hunspell + dansk ordbog"
$hunspell = Join-Path $tools "hunspell"
Copy-WithDlls "hunspell.exe" $hunspell
foreach ($ext in "aff", "dic") {
  Invoke-WebRequest -OutFile (Join-Path $hunspell "da_DK.$ext") -Uri "$dictUrl/da_DK.$ext"
}

Write-Host "== Tesseract + dansk sprogmodel"
$tesseract = Join-Path $tools "tesseract"
Copy-WithDlls "tesseract.exe" $tesseract
$tessdata = Join-Path $tesseract "tessdata"
New-Item -ItemType Directory -Force -Path $tessdata | Out-Null
foreach ($lang in "dan", "osd") {
  Invoke-WebRequest -OutFile (Join-Path $tessdata "$lang.traineddata") `
    -Uri "$tessdataUrl/$lang.traineddata"
}

@"
Programmer, der følger med Ordhjælp, og deres licenser:

hunspell\   Hunspell (MPL 1.1 / GPL 2 / LGPL 2.1) - https://hunspell.github.io
            Dansk ordbog fra LibreOffice (GPL 2) - https://github.com/LibreOffice/dictionaries
tesseract\  Tesseract OCR (Apache 2.0) - https://github.com/tesseract-ocr/tesseract
            Leptonica (BSD 2) og andre biblioteker fra MSYS2 - https://www.msys2.org
            Sprogmodeller fra tessdata_fast (Apache 2.0) - https://github.com/tesseract-ocr/tessdata_fast
"@ | ForEach-Object {
  [IO.File]::WriteAllText((Join-Path $tools "LICENSES.txt"), $_, (New-Object Text.UTF8Encoding $false))
}

Write-Host "== Røgtest uden MSYS2 i PATH"
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$word = "hus" | & (Join-Path $hunspell "hunspell.exe") -d (Join-Path $hunspell "da_DK") -G
if ($LASTEXITCODE -or "$word" -notmatch "hus") { throw "Hunspell virker ikke uden MSYS2 ($word)" }
& (Join-Path $tesseract "tesseract.exe") --tessdata-dir $tessdata --list-langs
if ($LASTEXITCODE) { throw "Tesseract virker ikke uden MSYS2" }
Write-Host "Færdig: $tools"
