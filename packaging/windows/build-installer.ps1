# Byg Windows-installeren: dist\Ordhjaelp-<version>-Setup.exe
# og zip-filen til at pakke ud og køre: dist\Ordhjaelp-<version>-Windows.zip
#
# Kræver uv og Inno Setup 6 (winget install JRSoftware.InnoSetup).
# Brug (fra repoets rod eller herfra):  powershell -File packaging\windows\build-installer.ps1
# -SkipInstaller bygger kun programmappen dist\Ordhjaelp\ (uden Inno Setup).
# Hunspell og Tesseract kommer med, hvis MSYS2 findes (se fetch-tools.ps1). -NoTools springer dem over.
param([switch]$SkipInstaller, [switch]$NoTools, [string]$Msys = "C:\msys64")

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$root = Resolve-Path (Join-Path $here "..\..")
Set-Location $root

$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
Write-Host "== Ordhjælp $version"

$build = Join-Path $here "build"
New-Item -ItemType Directory -Force -Path $build | Out-Null

Write-Host "== Ikon"
uv run --group windows-build python packaging\windows\make_icon.py `
  src\ordhjaelp\ui\icons\ordhjaelp.svg (Join-Path $build "ordhjaelp.ico")
if ($LASTEXITCODE) { throw "Ikonet kunne ikke laves" }

Write-Host "== Versionsoplysninger til Ordhjaelp.exe"
$parts = ($version -split '[^0-9]+' | Where-Object { $_ } | Select-Object -First 4)
while ($parts.Count -lt 4) { $parts += "0" }
$tuple = $parts -join ", "
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($tuple), prodvers=($tuple)),
  kids=[
    StringFileInfo([StringTable('040604B0', [
      StringStruct('CompanyName', 'Ordhjælp'),
      StringStruct('FileDescription', 'Ordhjælp – dansk læse- og skrivehjælp'),
      StringStruct('FileVersion', '$version'),
      StringStruct('ProductName', 'Ordhjælp'),
      StringStruct('ProductVersion', '$version'),
      StringStruct('LegalCopyright', 'GPL-3.0-or-later')])]),
    VarFileInfo([VarStruct('Translation', [1030, 1200])])
  ]
)
"@ | ForEach-Object {
  # Uden BOM: PyInstaller læser filen som Python-kode
  [IO.File]::WriteAllText((Join-Path $build "version.txt"), $_, (New-Object Text.UTF8Encoding $false))
}

Write-Host "== PyInstaller"
uv run --group windows-build python -m PyInstaller --noconfirm --clean `
  --distpath dist --workpath (Join-Path $build "pyinstaller") packaging\windows\ordhjaelp.spec
if ($LASTEXITCODE) { throw "PyInstaller fejlede" }

Write-Host "== Hunspell og Tesseract"
if (-not $NoTools -and (Test-Path (Join-Path $Msys "usr\bin\pacman.exe"))) {
  & (Join-Path $here "fetch-tools.ps1") -Msys $Msys
  Copy-Item -Recurse (Join-Path $build "tools") (Join-Path $root "dist\Ordhjaelp\tools")
} else {
  Write-Warning "Uden Hunspell og Tesseract: ordforslag uden navne med stort, og læs fra skærmen kræver, at Tesseract installeres"
}

Write-Host "== Røgtest: kan programmet starte og svare?"
$exe = Join-Path $root "dist\Ordhjaelp\Ordhjaelp.exe"
$proc = Start-Process $exe -ArgumentList "--help" -PassThru -Wait
if ($proc.ExitCode -ne 0) { throw "Ordhjaelp.exe --help fejlede ($($proc.ExitCode))" }

Write-Host "== Zip-fil (pak ud og kør, uden installation)"
Copy-Item (Join-Path $here "LAES-MIG.txt") (Join-Path $root "dist\Ordhjaelp\LAES-MIG.txt")
$zip = Join-Path $root "dist\Ordhjaelp-$version-Windows.zip"
if (Test-Path $zip) { Remove-Item $zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
# Med mappen Ordhjaelp\ øverst, så alt havner i én mappe, når den pakkes ud
[IO.Compression.ZipFile]::CreateFromDirectory(
  (Join-Path $root "dist\Ordhjaelp"), $zip, [IO.Compression.CompressionLevel]::Optimal, $true)
Write-Host "Zip: dist\Ordhjaelp-$version-Windows.zip"

if ($SkipInstaller) { Write-Host "Færdig: dist\Ordhjaelp\"; exit 0 }

Write-Host "== Inno Setup"
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
  $iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw "Inno Setup 6 mangler: winget install JRSoftware.InnoSetup" }
& $iscc /Qp "/DAppVersion=$version" (Join-Path $here "ordhjaelp.iss")
if ($LASTEXITCODE) { throw "Inno Setup fejlede" }

Write-Host "Færdig: dist\Ordhjaelp-$version-Setup.exe"
