"""Programmer, der følger med Windows-installeren (Hunspell og Tesseract).

Installeren lægger dem i en tools-mappe ved siden af Ordhjaelp.exe:

    tools\\hunspell\\hunspell.exe   + da_DK.aff og da_DK.dic
    tools\\tesseract\\tesseract.exe + tessdata\\dan.traineddata

Uden installeren (udviklingsmappen, RPM) bruges systemets programmer som før.
"""

from __future__ import annotations

import sys
from pathlib import Path


def tools_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    path = Path(sys.executable).parent / "tools"
    return path if path.is_dir() else None


def tool(name: str) -> Path | None:
    """tools\\<name>\\<name>.exe, hvis det følger med installeren."""
    base = tools_dir()
    if base is None:
        return None
    exe = base / name / f"{name}.exe"
    return exe if exe.is_file() else None
