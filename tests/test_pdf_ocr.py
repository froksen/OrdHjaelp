import ctypes
import os
import re
import shutil
import subprocess

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pypdfium2 as pdfium  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPageSize, QPainter, QPdfWriter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp.ocr.pdf import (  # noqa: E402
    AlreadySearchable,
    Cancelled,
    PdfOcrError,
    make_searchable,
    searchable_path,
)

SCANNED_TEXT = "Hunden løb over græsset i haven"
REAL_TEXT = "Dette er en almindelig side med rigtig tekst i"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _text_as_image(text: str) -> QImage:
    """Tekst som pixels – sådan ser en scannet side ud for en PDF."""
    image = QImage(1100, 300, QImage.Format.Format_RGB888)
    image.fill(QColor("white"))
    painter = QPainter(image)
    font = QFont("DejaVu Sans")
    font.setPixelSize(50)
    painter.setFont(font)
    painter.setPen(QColor("black"))
    painter.drawText(30, 150, text)
    painter.end()
    return image


def _add_text(doc, index, text):
    """Rigtig tekst med PDF'ens indbyggede Helvetica.

    Ikke med Qt: på Windows tegner Qt teksten som streger, når den kører uden
    skærm (offscreen), og så har siden ingen tekst, der kan udtrækkes.
    """
    raw = pdfium.raw
    page = doc[index]
    font = raw.FPDFText_LoadStandardFont(doc.raw, b"Helvetica")
    obj = raw.FPDFPageObj_CreateTextObj(doc.raw, font, 14.0)
    utf16 = ctypes.create_string_buffer((text + "\0").encode("utf-16-le"))
    raw.FPDFText_SetText(obj, ctypes.cast(utf16, ctypes.POINTER(raw.FPDF_WCHAR)))
    raw.FPDFPageObj_Transform(obj, 1, 0, 0, 1, 72, 700)
    raw.FPDFPage_InsertObject(page.raw, obj)
    raw.FPDFPage_GenerateContent(page.raw)
    page.close()


def make_pdf(path, pages):
    """pages: liste af ("scannet" | "tekst", tekst)."""
    drawn = path.with_suffix(".qt.pdf")
    writer = QPdfWriter(str(drawn))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(150)
    painter = QPainter(writer)
    for i, (kind, text) in enumerate(pages):
        if i:
            writer.newPage()
        if kind == "scannet":
            painter.drawImage(50, 50, _text_as_image(text))
    painter.end()
    doc = pdfium.PdfDocument(str(drawn))
    for i, (kind, text) in enumerate(pages):
        if kind == "tekst":
            _add_text(doc, i, text)
    doc.save(str(path))
    doc.close()
    drawn.unlink()
    return path


def fake_ocr(calls):
    """I stedet for Tesseract: en tom side i samme størrelse som billedet."""

    def run(image, out, dpi):
        calls.append(dpi)
        img = QImage(str(image))
        doc = pdfium.PdfDocument.new()
        doc.new_page(img.width() * 72 / dpi, img.height() * 72 / dpi)
        doc.save(str(out.with_suffix(".pdf")))
        doc.close()

    return run


def page_texts(path):
    doc = pdfium.PdfDocument(str(path))
    try:
        texts = []
        for page in doc:
            tp = page.get_textpage()
            texts.append(tp.get_text_bounded())
            tp.close()
        return texts
    finally:
        doc.close()


def page_sizes(path):
    doc = pdfium.PdfDocument(str(path))
    try:
        return [tuple(round(v) for v in page.get_size()) for page in doc]
    finally:
        doc.close()


def test_searchable_path_never_overwrites(tmp_path):
    src = tmp_path / "Opgave.pdf"
    assert searchable_path(src).name == "Opgave (søgbar).pdf"
    (tmp_path / "Opgave (søgbar).pdf").touch()
    assert searchable_path(src).name == "Opgave (søgbar 2).pdf"


def test_only_scanned_pages_get_ocr(app, tmp_path):
    src = make_pdf(tmp_path / "blandet.pdf", [("scannet", SCANNED_TEXT), ("tekst", REAL_TEXT)])
    dst = tmp_path / "ud.pdf"
    calls, seen = [], []
    count = make_searchable(src, dst, lambda d, t: seen.append((d, t)) or True, fake_ocr(calls))
    assert count == 1
    assert calls == [300]
    assert seen == [(0, 1), (1, 1)]
    texts = page_texts(dst)
    assert len(texts) == 2
    assert REAL_TEXT in texts[1]  # siden med tekst er kopieret uændret
    assert page_sizes(dst) == page_sizes(src)  # samme sidestørrelse som før
    assert list(tmp_path.glob("*.tmp")) == []


def test_already_searchable_writes_nothing(app, tmp_path):
    src = make_pdf(tmp_path / "tekst.pdf", [("tekst", REAL_TEXT)])
    dst = tmp_path / "ud.pdf"
    with pytest.raises(AlreadySearchable):
        make_searchable(src, dst, ocr_page=fake_ocr([]))
    assert not dst.exists()


def test_cancel_writes_nothing(app, tmp_path):
    src = make_pdf(tmp_path / "scan.pdf", [("scannet", SCANNED_TEXT)] * 3)
    dst = tmp_path / "ud.pdf"
    calls = []
    with pytest.raises(Cancelled):
        make_searchable(src, dst, lambda done, total: done < 1, fake_ocr(calls))
    assert len(calls) == 1  # stoppede efter første side
    assert not dst.exists()


def test_broken_file(tmp_path):
    src = tmp_path / "ødelagt.pdf"
    src.write_bytes(b"ikke en pdf")
    with pytest.raises(PdfOcrError, match="kunne ikke åbnes"):
        make_searchable(src, tmp_path / "ud.pdf", ocr_page=fake_ocr([]))


def test_real_tesseract_finds_danish_text(app, tmp_path):
    """Hele vejen med Tesseract og den danske sprogpakke (installeres i CI)."""
    src = make_pdf(tmp_path / "scan.pdf", [("scannet", SCANNED_TEXT), ("tekst", REAL_TEXT)])
    assert page_texts(src)[0].strip() == ""
    dst = tmp_path / "ud.pdf"
    assert make_searchable(src, dst) == 1
    texts = page_texts(dst)
    assert "Hunden løb over græsset" in " ".join(texts[0].split())
    assert REAL_TEXT in texts[1]
    assert page_sizes(dst) == page_sizes(src)


def _system_tessdata():
    """Mappen med Tesseracts sprogmodeller (fra "tesseract --list-langs")."""
    from ordhjaelp.ocr.tesseract import find_tesseract

    out = subprocess.run(
        [find_tesseract(), "--list-langs"], capture_output=True, text=True, check=False
    )
    match = re.search(r'"(.+?)"', out.stdout + out.stderr)
    assert match, out
    return match.group(1)


def test_works_with_tessdata_without_configs(app, tmp_path, monkeypatch):
    """Som Windows-installerens tessdata: kun sprogmodellen, ingen configs-mappe."""
    from ordhjaelp.ocr import pdf

    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    shutil.copy(os.path.join(_system_tessdata(), "dan.traineddata"), tessdata)
    monkeypatch.setattr(pdf, "_tessdata_args", lambda exe: ["--tessdata-dir", str(tessdata)])
    src = make_pdf(tmp_path / "scan.pdf", [("scannet", SCANNED_TEXT)])
    dst = tmp_path / "ud.pdf"
    assert make_searchable(src, dst) == 1
    assert "Hunden" in page_texts(dst)[0]


def _run_job(job):
    from PySide6.QtCore import QCoreApplication, QDeadlineTimer, QThread

    job.start()
    deadline = QDeadlineTimer(10000)
    while job.result == "ikke færdig" and not deadline.hasExpired():
        QCoreApplication.processEvents()
        QThread.msleep(10)
    return job


def test_job_saves_next_to_original_and_tells(app, tmp_path, monkeypatch):
    from ordhjaelp.ui import pdf_ocr

    src = make_pdf(tmp_path / "Opgave.pdf", [("scannet", SCANNED_TEXT)])
    real = pdf_ocr.make_searchable
    monkeypatch.setattr(pdf_ocr, "make_searchable", lambda s, d, p: real(s, d, p, fake_ocr([])))
    job = _run_job(pdf_ocr.PdfOcrJob(src))
    assert job.result is None
    assert (tmp_path / "Opgave (søgbar).pdf").is_file()
    assert "Opgave (søgbar).pdf" in job._box.text()
    job._box.close()


def test_job_explains_already_searchable(app, tmp_path):
    from ordhjaelp.ui import pdf_ocr

    src = make_pdf(tmp_path / "tekst.pdf", [("tekst", REAL_TEXT)])
    job = _run_job(pdf_ocr.PdfOcrJob(src))
    assert "allerede tekst" in job.result
    assert not job.dst.exists()
    job._box.close()


def test_job_stop_button_cancels(app, tmp_path, monkeypatch):
    from ordhjaelp.ui import pdf_ocr

    src = make_pdf(tmp_path / "scan.pdf", [("scannet", SCANNED_TEXT)] * 3)
    real = pdf_ocr.make_searchable
    job = pdf_ocr.PdfOcrJob(src)

    def press_stop_first(s, d, p):
        def ocr(image, out, dpi):
            job._cancel.set()  # som når eleven trykker Stop
            fake_ocr([])(image, out, dpi)

        return real(s, d, p, ocr)

    monkeypatch.setattr(pdf_ocr, "make_searchable", press_stop_first)
    _run_job(job)
    assert isinstance(job.result, Cancelled)
    assert not job.dst.exists()
