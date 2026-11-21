"""Tekstgenkendelse (OCR) med Tesseract og den færdige danske sprogmodel.

Kalder tesseract-programmet direkte (ingen ekstra Python-pakker).
Linux:   sudo dnf install tesseract tesseract-langpack-dan
Windows/macOS: Tesseract-installeren (senere i Ordhjælps egen installer).
"""

from __future__ import annotations

import re
import shutil
import subprocess

from ordhjaelp.services.screen_read import OcrUnavailable

_LINE_NOISE = re.compile(r"^[\W_]{1,3}$")  # linjer med kun et par tegn/streger


class TesseractOCR:
    def __init__(self, language: str = "dan") -> None:
        self._language = language

    @staticmethod
    def available() -> bool:
        return shutil.which("tesseract") is not None

    def recognize(self, png: bytes) -> str:
        if not self.available():
            raise OcrUnavailable("Tesseract er ikke installeret")
        result = subprocess.run(
            # --psm 6: én blok tekst – passer godt til et udsnit, eleven har markeret
            ["tesseract", "stdin", "stdout", "-l", self._language, "--psm", "6"],
            input=png,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            if "Failed loading language" in err:
                raise OcrUnavailable(f"Sprogpakken '{self._language}' til Tesseract mangler")
            raise RuntimeError(f"Tesseract fejlede: {err}")
        return clean_ocr_text(result.stdout.decode("utf-8", errors="replace"))


def clean_ocr_text(text: str) -> str:
    """Fjern støj-linjer, som OCR ofte finder i kanter og ikoner."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line and not _LINE_NOISE.match(line))
