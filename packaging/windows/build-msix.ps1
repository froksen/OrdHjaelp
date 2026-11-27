# Byg MSIX-pakken til Microsoft Store: dist\Ordhjaelp-<version>.msix
#
# Kræver, at programmappen er bygget først:
#   powershell -File packaging\windows\build-installer.ps1 -SkipInstaller
# og Windows SDK (makeappx.exe), som findes på GitHubs Windows-maskiner.
#
# Pakken er ikke signeret: Microsoft Store signerer den selv. Til afprøvning på egen
# computer skal den signeres med et testcertifikat (se store\README.md).
# Navn og udgiver står i store\identitet.toml.

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$root = Resolve-Path (Join-Path $here "..\..")
Set-Location $root

$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
$app = Join-Path $root "dist\Ordhjaelp"
if (-not (Test-Path (Join-Path $app "Ordhjaelp.exe"))) {
  throw "dist\Ordhjaelp mangler. Byg først med build-installer.ps1 -SkipInstaller"
}

Write-Host "== Kopi af programmappen"
$stage = Join-Path $here "build\msix"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
Copy-Item -Recurse $app $stage

Write-Host "== Manifest og logoer"
uv run --group windows-build python packaging\windows\store\make_msix.py $stage --version $version
if ($LASTEXITCODE) { throw "make_msix.py fejlede" }

Write-Host "== makeappx"
$makeappx = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\makeappx.exe" -ErrorAction SilentlyContinue |
  Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) { throw "makeappx.exe mangler: installér Windows SDK" }
$msix = Join-Path $root "dist\Ordhjaelp-$version.msix"
& $makeappx.FullName pack /o /d $stage /p $msix
if ($LASTEXITCODE) { throw "makeappx fejlede" }
Write-Host "Færdig: dist\Ordhjaelp-$version.msix"
