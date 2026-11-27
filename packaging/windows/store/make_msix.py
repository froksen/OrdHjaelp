"""Gør programmappen klar til en MSIX-pakke: AppxManifest.xml og logoerne i Assets\\.

Brug:
  python make_msix.py <mappe> --version 0.4.0.1   (mappen er en kopi af dist\\Ordhjaelp)
  python make_msix.py --vis udgiver                (til afprøvningen i CI)

Navn, udgiver og visningsnavn står i identitet.toml ved siden af dette script.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
ICON = ROOT / "src" / "ordhjaelp" / "ui" / "icons" / "ordhjaelp.svg"
STARTUP_TASK_ID = "OrdhjaelpStart"  # samme som i src/ordhjaelp/platform/windows/store.py

# Logoerne, Windows og Store kræver: filnavn -> størrelse i punkter
ASSETS = {
    "StoreLogo.png": 50,
    "Square44x44Logo.png": 44,
    "Square150x150Logo.png": 150,
}
FIELDS = ("navn", "udgiver", "udgiver_visning", "visningsnavn", "beskrivelse")


def store_version(version: str) -> str:
    """Ordhjælps version (fx 0.4.0.1) som MSIX-version a.b.c.0.

    Microsoft Store kræver, at det sidste tal er 0. Derfor bliver de to sidste tal lagt
    sammen: 0.4.0.1 -> 0.4.1.0 og 0.4.2.3 -> 0.4.203.0. Rækkefølgen bevares, så
    længe det sidste tal er under 100.
    """
    parts = [int(p) for p in version.split(".")]
    if len(parts) > 4 or not parts:
        raise ValueError(f"Ukendt version: {version}")
    major, minor, patch, revision = (parts + [0, 0, 0, 0])[:4]
    if revision >= 100:
        raise ValueError(f"Det sidste tal i {version} skal være under 100")
    build = patch * 100 + revision
    for value in (major, minor, build):
        if not 0 <= value <= 65535:
            raise ValueError(f"MSIX-versionen af {version} bliver for stor")
    return f"{major}.{minor}.{build}.0"


def identity(path: Path = HERE / "identitet.toml") -> dict[str, str]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    missing = [f for f in FIELDS if not str(raw.get(f, "")).strip()]
    if missing:
        raise ValueError(f"identitet.toml mangler: {', '.join(missing)}")
    return {f: str(raw[f]) for f in FIELDS}


def manifest(version: str, ident: dict[str, str]) -> str:
    text = (HERE / "AppxManifest.xml.in").read_text(encoding="utf-8")
    values = {
        "VERSION": store_version(version),
        "STARTUP_TASK_ID": STARTUP_TASK_ID,
        **{field.upper(): value for field, value in ident.items()},
    }
    for key, value in values.items():
        text = text.replace(f"@{key}@", escape(value, {'"': "&quot;"}))
    if "@" in text.split("-->", 1)[1]:
        raise ValueError("En pladsholder i AppxManifest.xml.in blev ikke udfyldt")
    return text


def make_assets(folder: Path) -> None:
    """Tegn programmets ikon i de størrelser, pakken skal bruge (med lidt luft om)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    _app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(ICON))
    if not renderer.isValid():
        raise ValueError(f"Kan ikke læse {ICON}")
    folder.mkdir(parents=True, exist_ok=True)
    for name, size in ASSETS.items():
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = size * 0.08
        renderer.render(painter, QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
        painter.end()
        if not image.save(str(folder / name), "PNG"):
            raise OSError(f"Kan ikke gemme {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mappe", nargs="?", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--vis", choices=FIELDS, help="skriv én værdi fra identitet.toml")
    args = parser.parse_args(argv)
    ident = identity()
    if args.vis:
        print(ident[args.vis])
        return 0
    if args.mappe is None or args.version is None:
        parser.error("mappe og --version skal angives")
    if not (args.mappe / "Ordhjaelp.exe").exists():
        print(f"Ordhjaelp.exe findes ikke i {args.mappe}", file=sys.stderr)
        return 1
    (args.mappe / "AppxManifest.xml").write_text(manifest(args.version, ident), encoding="utf-8")
    make_assets(args.mappe / "Assets")
    print(f"MSIX-version {store_version(args.version)} for {ident['visningsnavn']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
