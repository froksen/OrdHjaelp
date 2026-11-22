"""Winget-manifesterne skal passe med installeren og hinanden."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINGET = ROOT / "packaging" / "windows" / "winget"
ISS = ROOT / "packaging" / "windows" / "ordhjaelp.iss"
PKG = "OleFrandsen.Ordhjaelp"


def _field(text: str, name: str) -> str:
    match = re.search(rf"^\s*-?\s*{name}: (.+)$", text, re.MULTILINE)
    assert match, f"{name} mangler"
    return match.group(1).strip().strip("'")


def _manifests() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in WINGET.glob("*.yaml")}


def test_all_manifests_same_package_and_version() -> None:
    manifests = _manifests()
    assert set(manifests) == {
        f"{PKG}.yaml",
        f"{PKG}.installer.yaml",
        f"{PKG}.locale.da-DK.yaml",
        f"{PKG}.locale.en-US.yaml",
    }
    versions = {_field(t, "PackageVersion") for t in manifests.values()}
    assert len(versions) == 1
    assert {_field(t, "PackageIdentifier") for t in manifests.values()} == {PKG}


def test_product_code_matches_inno_app_id() -> None:
    app_id = re.search(r"^AppId=\{(\{[0-9A-F-]+\})$", ISS.read_text(encoding="utf-8-sig"), re.M)
    assert app_id
    installer = _manifests()[f"{PKG}.installer.yaml"]
    assert _field(installer, "ProductCode") == f"{app_id.group(1)}_is1"


def test_installer_url_points_at_release_setup() -> None:
    installer = _manifests()[f"{PKG}.installer.yaml"]
    version = _field(installer, "PackageVersion")
    assert _field(installer, "InstallerUrl") == (
        f"https://github.com/froksen/OrdHj-lp/releases/download/v{version}/Ordhjaelp-{version}-Setup.exe"
    )
    assert re.fullmatch(r"[0-9A-F]{64}", _field(installer, "InstallerSha256"))
    # Installeren er pr. bruger (PrivilegesRequired=lowest), og det skal winget vide
    assert _field(installer, "Scope") == "user"
