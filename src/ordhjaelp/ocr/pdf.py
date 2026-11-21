"""Gør en scannet PDF søgbar: læg et usynligt tekstlag over siderne.

Sider, der allerede har tekst, kopieres uændret. Sider uden tekst (scannede) bliver
til billeder med pypdfium2, og Tesseract laver hver af dem om til en PDF-side med
billedet og et usynligt tekstlag. Bagefter samles det hele i én ny fil.

Så kan teksten markeres og læses op med Ordhjælps almindelige funktioner.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import pypdfium2 as pdfium

from ordhjaelp.ocr.tesseract import _tessdata_args, find_tesseract
from ordhjaelp.services.screen_read import OcrUnavailable

log = logging.getLogger(__name__)

DPI = 300  # god opløsning til Tesseract
MAX_PIXELS = 7000  # længste side i pixels; store plakater gøres mindre
MIN_LETTERS = 20  # så mange bogstaver skal en side have for at tælle som "har tekst"
JPEG_QUALITY = 80  # billedet i den nye PDF: god kvalitet uden en kæmpe fil

# Gør én side (et billede) til en PDF med tekstlag: (billede, ud-fil uden .pdf, dpi)
PageOcr = Callable[[Path, Path, int], None]
# Fortæl, hvor langt vi er: (sider færdige, sider i alt). Returnér False for at stoppe.
Progress = Callable[[int, int], bool]


class PdfOcrError(RuntimeError):
    """Noget gik galt. Beskeden kan vises direkte til eleven."""


class AlreadySearchable(PdfOcrError):
    """Alle sider har allerede tekst."""


class Cancelled(Exception):
    """Eleven trykkede på Stop."""


def searchable_path(src: Path) -> Path:
    """Navnet på den nye fil: "Opgave (søgbar).pdf" ved siden af originalen."""
    candidate = src.with_name(f"{src.stem} (søgbar).pdf")
    number = 2
    while candidate.exists():
        candidate = src.with_name(f"{src.stem} (søgbar {number}).pdf")
        number += 1
    return candidate


def page_has_text(page: pdfium.PdfPage) -> bool:
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_bounded()
    finally:
        textpage.close()
    return sum(ch.isalnum() for ch in text) >= MIN_LETTERS


def make_searchable(
    src: Path,
    dst: Path,
    progress: Progress | None = None,
    ocr_page: PageOcr | None = None,
    language: str = "dan",
) -> int:
    """Skriv en søgbar kopi af src til dst. Returnerer antallet af sider, der fik OCR.

    :raises OcrUnavailable: Tesseract mangler.
    :raises AlreadySearchable: alle sider har allerede tekst (intet skrevet).
    :raises Cancelled: progress returnerede False (intet skrevet).
    :raises PdfOcrError: filen kunne ikke læses eller skrives.
    """
    if ocr_page is None:
        ocr_page = _tesseract_page(language)
    try:
        source = pdfium.PdfDocument(str(src))
    except pdfium.PdfiumError as exc:
        raise PdfOcrError(
            "PDF'en kunne ikke åbnes. Den er måske låst med en adgangskode eller ødelagt."
        ) from exc
    try:
        scanned = [i for i in range(len(source)) if not page_has_text(source[i])]
        if not scanned:
            raise AlreadySearchable("Denne PDF har allerede tekst. Den kan læses op, som den er.")
        log.info("OCR af %d af %d sider i %s", len(scanned), len(source), src)
        with tempfile.TemporaryDirectory(prefix="ordhjaelp-pdf-") as tmp:
            result = _build(source, scanned, Path(tmp), ocr_page, progress)
            try:
                _save(result, dst)
            finally:
                result.close()
    finally:
        source.close()
    return len(scanned)


def _build(
    source: pdfium.PdfDocument,
    scanned: list[int],
    tmp: Path,
    ocr_page: PageOcr,
    progress: Progress | None,
) -> pdfium.PdfDocument:
    """Ny PDF: sider med tekst fra originalen, scannede sider fra Tesseract."""
    total = len(scanned)
    todo = set(scanned)
    if progress is not None and not progress(0, total):
        raise Cancelled
    result = pdfium.PdfDocument.new()
    ocr_docs: list[pdfium.PdfDocument] = []
    try:
        done = 0
        for index in range(len(source)):
            if index not in todo:
                result.import_pages(source, [index])
                continue
            image = tmp / f"side{index}.jpg"
            dpi = _render(source[index], image)
            out = tmp / f"side{index}"
            ocr_page(image, out, dpi)
            page_pdf = pdfium.PdfDocument(str(out.with_suffix(".pdf")))
            ocr_docs.append(page_pdf)  # skal være åben, til result er gemt
            result.import_pages(page_pdf)
            image.unlink(missing_ok=True)
            done += 1
            if progress is not None and not progress(done, total):
                raise Cancelled
    except BaseException:
        result.close()
        raise
    finally:
        for doc in ocr_docs:
            doc.close()
    return result


def _render(page: pdfium.PdfPage, image: Path) -> int:
    """Gem siden som JPEG. Returnerer opløsningen (dpi), så sidens størrelse bevares."""
    from PySide6.QtGui import QImage

    width, height = page.get_size()  # i punkter (1/72 tomme)
    scale = min(DPI / 72, MAX_PIXELS / max(width, height, 1))
    bitmap = page.render(scale=scale, rev_byteorder=True, may_draw_forms=True)
    try:
        pixels = bitmap.to_numpy()
        h, w = pixels.shape[:2]
        fmt = QImage.Format.Format_RGB888 if pixels.ndim == 3 else QImage.Format.Format_Grayscale8
        if pixels.ndim == 3 and pixels.shape[2] == 4:
            fmt = QImage.Format.Format_RGBA8888
        qimage = QImage(pixels.data, w, h, bitmap.stride, fmt)
        dpi = round(scale * 72)
        qimage.setDotsPerMeterX(round(dpi / 0.0254))
        qimage.setDotsPerMeterY(round(dpi / 0.0254))
        if not qimage.save(str(image), "JPEG", JPEG_QUALITY):
            raise PdfOcrError("Siden kunne ikke laves om til et billede.")
    finally:
        bitmap.close()
    return dpi


def _tesseract_page(language: str) -> PageOcr:
    exe = find_tesseract()
    if exe is None:
        raise OcrUnavailable("Tesseract er ikke installeret")

    def run(image: Path, out: Path, dpi: int) -> None:
        result = subprocess.run(
            [exe, *_tessdata_args(exe), str(image), str(out), "-l", language]
            + ["--dpi", str(dpi)]
            # Ikke konfigurationsfilen "pdf": den mangler, når tessdata kun har
            # sprogmodellerne (fx i Windows-installeren)
            + ["-c", "tessedit_create_pdf=1", "-c", "tessedit_create_txt=0"],
            capture_output=True,
            timeout=300,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not out.with_suffix(".pdf").is_file():
            err = result.stderr.decode("utf-8", errors="replace").strip()
            if "Failed loading language" in err:
                raise OcrUnavailable(f"Sprogpakken '{language}' til Tesseract mangler")
            raise PdfOcrError(f"Tekstgenkendelsen fejlede: {err[-300:]}")

    return run


def _save(doc: pdfium.PdfDocument, dst: Path) -> None:
    """Gem via en midlertidig fil, så der aldrig ligger en halv PDF."""
    tmp = dst.with_name(dst.name + ".tmp")
    try:
        doc.save(str(tmp))
        tmp.replace(dst)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise PdfOcrError(f"Den nye PDF kunne ikke gemmes i {dst.parent}.") from exc
