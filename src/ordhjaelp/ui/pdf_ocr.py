"""Gør en PDF søgbar: vælg filen, se hvor langt den er, og åbn resultatet."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QWidget

from ordhjaelp.ocr.pdf import (
    AlreadySearchable,
    Cancelled,
    PdfOcrError,
    make_searchable,
    searchable_path,
)
from ordhjaelp.services.screen_read import OcrUnavailable

log = logging.getLogger(__name__)

TITLE = "Gør en PDF søgbar"
MSG_DONE = (
    "Færdig! Nu kan teksten markeres og læses op.\n\n"
    "Den nye PDF hedder:\n{name}\n\nDen ligger samme sted som den gamle."
)
MSG_ALREADY = "\n\nPDF'en hedder:\n{name}"
MSG_WHAT_NOW = "\n\nVil du åbne den?"
# Hvad der skal ske bagefter
OPEN_PDF = "pdf"
OPEN_FOLDER = "mappe"
MSG_NO_OCR = "Tekstgenkendelse (Tesseract) er ikke installeret på computeren."
MSG_ERROR = "Det gik galt. Prøv igen, eller prøv en anden PDF."


class _Bridge(QObject):
    progress = Signal(int, int)
    finished = Signal(object)  # None = færdig, ellers en besked (str) eller Cancelled


class PdfOcrJob:
    """Ét job: kører i en baggrundstråd og viser fremskridt i et lille vindue."""

    def __init__(self, src: Path, parent: QWidget | None = None) -> None:
        self.src = src
        self.dst = searchable_path(src)
        self._cancel = threading.Event()
        self._bridge = _Bridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.finished.connect(self._on_finished)
        self.dialog = QProgressDialog(f"Finder teksten i {src.name} …", "Stop", 0, 0, parent)
        self.dialog.setWindowTitle(TITLE)
        self.dialog.setMinimumDuration(0)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)
        self.dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.dialog.canceled.connect(self._cancel.set)
        self.result: object = "ikke færdig"
        self.on_done = lambda: None  # kaldes, når eleven har lukket beskeden

    def start(self) -> None:
        self.dialog.show()
        threading.Thread(target=self._work, daemon=True, name="pdf-ocr").start()

    def _work(self) -> None:
        def progress(done: int, total: int) -> bool:
            self._bridge.progress.emit(done, total)
            return not self._cancel.is_set()

        try:
            make_searchable(self.src, self.dst, progress)
            outcome: object = None
        except Cancelled as exc:
            outcome = exc
        except AlreadySearchable as exc:
            outcome = exc  # den gamle PDF kan bruges, som den er
        except PdfOcrError as exc:
            outcome = str(exc)
        except OcrUnavailable as exc:
            log.warning("%s", exc)
            outcome = MSG_NO_OCR
        except Exception:
            log.exception("PDF-OCR fejlede")
            outcome = MSG_ERROR
        self._bridge.finished.emit(outcome)

    def _on_progress(self, done: int, total: int) -> None:
        self.dialog.setMaximum(total)
        self.dialog.setValue(done)
        self.dialog.setLabelText(f"Finder teksten i {self.src.name} …\nSide {done} af {total}")

    def _on_finished(self, outcome: object) -> None:
        self.result = outcome
        self.dialog.close()
        parent = self.dialog.parentWidget()
        if outcome is None:
            box = self._ask_open(self.dst, MSG_DONE.format(name=self.dst.name), parent)
        elif isinstance(outcome, AlreadySearchable):
            box = self._ask_open(
                self.src, str(outcome) + MSG_ALREADY.format(name=self.src.name), parent
            )
        elif isinstance(outcome, Cancelled):
            self._finish()
        else:
            box = QMessageBox(QMessageBox.Icon.Warning, TITLE, str(outcome), parent=parent)
            box.finished.connect(lambda _: self._finish())
            box.show()
        self._box = box if not isinstance(outcome, Cancelled) else None

    def _ask_open(self, pdf: Path, text: str, parent: QWidget | None) -> QMessageBox:
        """Spørg, om PDF'en skal åbnes i PDF-læseren, om mappen skal åbnes, eller ingen af dem."""
        box = QMessageBox(QMessageBox.Icon.Information, TITLE, text + MSG_WHAT_NOW, parent=parent)
        choices = {
            box.addButton("Åbn PDF'en", QMessageBox.ButtonRole.AcceptRole): OPEN_PDF,
            box.addButton("Åbn mappen", QMessageBox.ButtonRole.ActionRole): OPEN_FOLDER,
        }
        box.addButton("Nej tak", QMessageBox.ButtonRole.RejectRole)
        box.finished.connect(lambda _: self._finish(pdf, choices.get(box.clickedButton())))
        box.show()
        return box

    def _finish(self, pdf: Path | None = None, choice: str | None = None) -> None:
        if pdf is not None and choice == OPEN_PDF:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf)))
        elif pdf is not None and choice == OPEN_FOLDER:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf.parent)))
        self.on_done()


def choose_pdf(parent: QWidget | None = None) -> Path | None:
    name, _ = QFileDialog.getOpenFileName(
        parent, "Vælg den PDF, der skal gøres søgbar", str(Path.home()), "PDF (*.pdf)"
    )
    return Path(name) if name else None
