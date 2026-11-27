"""Vælg og hent sprogmodeller: listen til velkomstguiden og administrationen.

Begge vinduer bruger samme liste. I velkomstguiden (ui/welcome.py) vælger man med
flueben; i administrationen (fra indstillingerne) henter og sletter man enkeltvis.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ordhjaelp.config import Config
from ordhjaelp.models.catalog import Kind, ModelInfo, of_kind, size_text
from ordhjaelp.models.store import ModelStore

log = logging.getLogger(__name__)

SECTION_TITLES = {
    Kind.VOICE: ("Stemme", "Bruges til at læse tekst op."),
    Kind.SPEECH: (
        "Talegenkendelse",
        "Bruges til diktering. Vælg én – eller flere at skifte mellem.",
    ),
}
NETWORK_HELP = "Tjek at computeren har forbindelse til internettet, og prøv igen."


class _Downloader(QObject):
    """Henter modeller én ad gangen i baggrunden og melder tilbage via Qt-signaler."""

    progress = Signal(str, float)  # model-id, 0–1
    finished = Signal(str, str)  # model-id, fejltekst ("" = ok)

    def __init__(self, store: ModelStore) -> None:
        super().__init__()
        self._store = store
        self.busy = False

    def start(self, models: list[ModelInfo]) -> None:
        self.busy = True
        threading.Thread(target=self._run, args=(models,), daemon=True, name="hent").start()

    def _run(self, models: list[ModelInfo]) -> None:
        try:
            for model in models:
                try:
                    self._store.download(model, lambda f, m=model: self.progress.emit(m.id, f))
                except Exception as exc:  # noqa: BLE001 - vises for brugeren
                    log.exception("Kunne ikke hente %s", model.title)
                    self.finished.emit(model.id, str(exc) or exc.__class__.__name__)
                    return
                self.finished.emit(model.id, "")
        finally:
            self.busy = False


class _ModelRow(QFrame):
    def __init__(self, model: ModelInfo, choose: bool) -> None:
        super().__init__()
        self.model = model
        self.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(self)
        title = QLabel(
            f"<b>{model.title}</b>  <span style='color: gray'>"
            f"{size_text(model.size_mb)}</span>"
            + ("  <i>(anbefalet)</i>" if model.recommended else "")
        )
        desc = QLabel(model.description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: gray")
        self.check = QCheckBox() if choose else None
        self.status = QLabel()
        self.button = QPushButton() if not choose else None
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setVisible(False)
        if self.check:
            grid.addWidget(self.check, 0, 0, 2, 1)
        grid.addWidget(title, 0, 1)
        grid.addWidget(desc, 1, 1)
        grid.addWidget(self.status, 0, 2, Qt.AlignmentFlag.AlignRight)
        if self.button:
            grid.addWidget(self.button, 1, 2, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.bar, 2, 1, 1, 2)
        grid.setColumnStretch(1, 1)


class _ModelList(QScrollArea):
    def __init__(self, choose: bool, kinds: list[Kind] | None = None) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        col = QVBoxLayout(inner)
        self.rows: dict[str, _ModelRow] = {}
        for kind in kinds if kinds is not None else (Kind.VOICE, Kind.SPEECH):
            heading, explanation = SECTION_TITLES[kind]
            col.addWidget(QLabel(f"<h3>{heading}</h3>"))
            note = QLabel(explanation)
            note.setStyleSheet("color: gray")
            col.addWidget(note)
            for model in of_kind(kind):
                row = _ModelRow(model, choose)
                self.rows[model.id] = row
                col.addWidget(row)
        col.addStretch()
        self.setWidget(inner)
        self.setMinimumSize(560, 420)


def needs_first_run(store: ModelStore, cfg: Config) -> bool:
    """Mangler der modeller til det, der er slået til (og det, Ordhjælp bruges til)?"""
    from ordhjaelp.models.catalog import get

    if cfg.needs_voice:
        voice = next((m for m in of_kind(Kind.VOICE) if m.source == cfg.voice), None)
        if voice is None or not store.is_installed(voice):
            return True
    speech = get(cfg.dictation_model)
    return bool(cfg.dictation_active and speech and not store.is_installed(speech))


# -- administration fra indstillingerne -------------------------------------
class ModelManagerDialog(QDialog):
    def __init__(
        self, store: ModelStore, cfg: Config, on_changed: Callable[[], None] | None = None
    ) -> None:
        super().__init__()
        self._store = store
        self._cfg = cfg
        self._on_changed = on_changed or (lambda: None)
        self._pending: list[ModelInfo] = []
        self.setWindowTitle("Ordhjælp – sprogmodeller")
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Hent flere sprogmodeller, eller slet dem, der ikke bruges, for at spare plads."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = _ModelList(choose=False)
        layout.addWidget(self.list, 1)
        close = QPushButton("Luk")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)

        self._downloader = _Downloader(store)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished.connect(self._on_finished)
        for model_row in self.list.rows.values():
            assert model_row.button is not None
            model_row.button.clicked.connect(lambda _=False, r=model_row: self._clicked(r))
            self._refresh(model_row)

    def _in_use(self, model: ModelInfo) -> bool:
        if model.kind is Kind.VOICE:
            return model.source == self._cfg.voice
        return model.id == self._cfg.dictation_model and self._cfg.dictation_enabled

    def _refresh(self, row: _ModelRow) -> None:
        assert row.button is not None
        model = row.model
        if model in self._pending:
            row.status.setText("Venter …")
            row.button.setEnabled(False)
        elif self._store.is_installed(model):
            row.status.setText("✓ Hentet" + ("  (bruges nu)" if self._in_use(model) else ""))
            row.button.setText("Slet")
            row.button.setEnabled(not self._in_use(model))
            row.button.setToolTip("Bruges nu – vælg en anden først" if self._in_use(model) else "")
        else:
            row.status.setText("")
            row.button.setText("Hent")
            row.button.setEnabled(True)
            row.button.setToolTip("")

    def _clicked(self, row: _ModelRow) -> None:
        model = row.model
        if self._store.is_installed(model):
            answer = QMessageBox.question(
                self, "Slet?", f"Vil du slette {model.title} ({size_text(model.size_mb)})?"
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    self._store.delete(model)
                except OSError:
                    log.exception("Kunne ikke slette %s", model.title)
                self._refresh(row)
                self._on_changed()
            return
        self._pending.append(model)
        self._refresh(row)
        if not self._downloader.busy:
            self._next()

    def _next(self) -> None:
        if self._pending:
            self._downloader.start([self._pending[0]])

    def _on_progress(self, model_id: str, fraction: float) -> None:
        row = self.list.rows[model_id]
        row.bar.setVisible(True)
        row.bar.setValue(int(fraction * 100))
        row.status.setText("Henter …")

    def _on_finished(self, model_id: str, error: str) -> None:
        row = self.list.rows[model_id]
        row.bar.setVisible(False)
        self._pending = [m for m in self._pending if m.id != model_id]
        if error:
            QMessageBox.warning(
                self, "Kunne ikke hente", f"{row.model.title} kunne ikke hentes.\n\n{NETWORK_HELP}"
            )
        self._refresh(row)
        self._on_changed()
        self._next()

    def reject(self) -> None:  # noqa: D102
        self.accept()

    def accept(self) -> None:  # noqa: D102
        if self._downloader.busy:
            QMessageBox.information(
                self, "Henter stadig", "Vent til hentningen er færdig, før du lukker."
            )
            return
        super().accept()
