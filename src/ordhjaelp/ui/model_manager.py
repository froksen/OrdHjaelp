"""Vælg og hent sprogmodeller: velkomstvindue ved første start + administration.

Begge vinduer bruger samme liste. I velkomstvinduet vælger man med flueben;
i administrationen (fra indstillingerne) henter og sletter man enkeltvis.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ordhjaelp.config import Config, save_config
from ordhjaelp.models.catalog import CATALOG, Kind, ModelInfo, of_kind, size_text
from ordhjaelp.models.store import ModelStore
from ordhjaelp.platform.base import Autostart

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
    def __init__(self, choose: bool) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        col = QVBoxLayout(inner)
        self.rows: dict[str, _ModelRow] = {}
        for kind in (Kind.VOICE, Kind.SPEECH):
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


# -- velkomstvindue ved første start ----------------------------------------
class _BasicSettings(QGroupBox):
    """Grundindstillingerne, så alt det vigtigste kan vælges første gang."""

    def __init__(self, cfg: Config, autostart: Autostart | None) -> None:
        super().__init__("Grundindstillinger (kan ændres senere under Indstillinger)")
        grid = QGridLayout(self)
        self.autostart = QCheckBox("Start Ordhjælp, når der logges ind")
        self.autostart.setChecked(autostart is not None)
        self.autostart.setVisible(autostart is not None)
        self.prediction = QCheckBox("Vis ordforslag, mens der skrives")
        self.prediction.setChecked(cfg.prediction_enabled)
        self.read_word = QCheckBox("Læs ordet op ved mellemrum")
        self.read_word.setChecked(cfg.read_word_on_space)
        self.read_sentence = QCheckBox("Læs sætningen op ved punktum")
        self.read_sentence.setChecked(cfg.read_sentence_on_period)
        self.read_on_select = QCheckBox("Læs op, når der markeres tekst")
        self.read_on_select.setChecked(cfg.read_on_select)
        self.read_at_pointer = QCheckBox("Læs under musen med genveje")
        self.read_at_pointer.setChecked(cfg.read_at_pointer)
        # Windows 11 gemmer nye ikoner under ^. Kun brugeren kan vise dem, så
        # Ordhjælp viser vejledningen lige efter start, når ikonerne findes.
        self.tray_icons = QCheckBox("Vis Ordhjælps ikoner ved uret (ikke gemt under ^)")
        self.tray_icons.setChecked(True)
        # Windows lader ikke programmer gøre det selv: forklar, hvordan man gør
        self.tray_icons_how = QPushButton("Se hvordan …")
        self.tray_icons_how.setToolTip("Vejledning: sådan vises ikonerne ved uret")
        self.tray_icons_how.clicked.connect(self._show_tray_help)
        self.tray_icons_note = QLabel(
            "Windows lader kun dig selv vise ikonerne. Lige efter start viser Ordhjælp,\n"
            "hvordan du trækker dem frem fra ^ ved uret. Det tager et øjeblik."
        )
        self.tray_icons_note.setStyleSheet("color: gray")
        for widget in (self.tray_icons, self.tray_icons_how, self.tray_icons_note):
            widget.setVisible(sys.platform == "win32")
        boxes = [
            self.autostart,
            self.prediction,
            self.read_word,
            self.read_sentence,
            self.read_on_select,
            self.read_at_pointer,
        ]
        for i, box in enumerate(boxes):
            grid.addWidget(box, i // 2, i % 2)
        row = len(boxes) // 2
        grid.addWidget(self.tray_icons, row, 0)
        grid.addWidget(self.tray_icons_how, row, 1, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.tray_icons_note, row + 1, 0, 1, 2)

    def _show_tray_help(self) -> None:
        from ordhjaelp.platform import open_tray_icon_settings
        from ordhjaelp.ui.tray_help import TrayIconsHelpDialog

        TrayIconsHelpDialog(open_tray_icon_settings, self).exec()

    def apply(self, cfg: Config) -> None:
        cfg.prediction_enabled = self.prediction.isChecked()
        cfg.read_word_on_space = self.read_word.isChecked()
        cfg.read_sentence_on_period = self.read_sentence.isChecked()
        cfg.read_on_select = self.read_on_select.isChecked()
        cfg.read_at_pointer = self.read_at_pointer.isChecked()


class FirstRunDialog(QDialog):
    """Velkomst: vælg sprogmodeller og grundindstillinger, før Ordhjælp bruges første gang."""

    def __init__(self, store: ModelStore, cfg: Config, autostart: Autostart | None = None) -> None:
        super().__init__()
        self._store = store
        self._cfg = cfg
        self._autostart = autostart
        self._queue: list[ModelInfo] = []
        self._total_mb = 0
        self._done_mb = 0
        self.setWindowTitle("Velkommen til Ordhjælp")
        layout = QVBoxLayout(self)
        intro = QLabel(
            "<h2>Velkommen til Ordhjælp</h2>"
            "Ordhjælp skal hente nogle sprogmodeller, før den kan bruges. De hentes "
            "<b>én gang</b> og virker derefter uden internet.<br>"
            "Flere kan hentes senere under <i>Indstillinger → Sprogmodeller</i>."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list = _ModelList(choose=True)
        # Listen kan rulles: lad den give plads, så vinduet passer på små skærme
        # (skole-pc'er med 1366x768 og 125 % har kun ca. 614 punkter i højden)
        self.list.setMinimumHeight(160)
        layout.addWidget(self.list, 1)
        self._installed: set[str] = set()
        for row in self.list.rows.values():
            installed = store.is_installed(row.model)
            if installed:
                self._installed.add(row.model.id)
            assert row.check is not None
            row.check.setChecked(installed or row.model.recommended)
            if installed:
                row.check.setEnabled(False)
                row.status.setText("✓ Hentet")
            row.check.toggled.connect(self._update_summary)
        # En stemme er nødvendig: er der kun én, kan den ikke fravælges
        voices = of_kind(Kind.VOICE)
        if len(voices) == 1:
            only = self.list.rows[voices[0].id]
            assert only.check is not None
            only.check.setChecked(True)
            only.check.setEnabled(False)
            if not only.status.text():
                only.status.setText("Påkrævet")

        self.basics = _BasicSettings(cfg, autostart)
        layout.addWidget(self.basics)

        self.summary = QLabel()
        self.overall = QProgressBar()
        self.overall.setRange(0, 100)
        self.overall.setVisible(False)
        layout.addWidget(self.summary)
        layout.addWidget(self.overall)

        buttons = QHBoxLayout()
        self.quit_button = QPushButton("Afslut")
        self.quit_button.clicked.connect(self.reject)
        self.start_button = QPushButton("Hent og start")
        self.start_button.setDefault(True)
        self.start_button.clicked.connect(self._start)
        buttons.addStretch()
        buttons.addWidget(self.quit_button)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)

        self._downloader = _Downloader(store)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished.connect(self._on_finished)
        self._update_summary()
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        """Så højt som indholdet, men aldrig højere end skærmen."""
        size = self.sizeHint()
        screen = self.screen()
        if screen is not None:
            size.setHeight(min(size.height(), int(screen.availableGeometry().height() * 0.9)))
        self.resize(size)

    def chosen(self, only_missing: bool = False) -> list[ModelInfo]:
        result = []
        for row in self.list.rows.values():
            assert row.check is not None
            if row.check.isChecked() and not (only_missing and row.model.id in self._installed):
                result.append(row.model)
        return result

    def _update_summary(self) -> None:
        missing = self.chosen(only_missing=True)
        mb = sum(m.size_mb for m in missing)
        has_voice = any(m.kind is Kind.VOICE for m in self.chosen())
        self.start_button.setEnabled(has_voice)
        if not has_voice:
            self.summary.setText("Vælg mindst én stemme.")
        elif missing:
            self.summary.setText(f"Der skal hentes {size_text(mb)}.")
        else:
            self.summary.setText("Alt er hentet.")
            self.start_button.setText("Start")

    def _start(self) -> None:
        self._queue = self.chosen(only_missing=True)
        if not self._queue:
            self._finish()
            return
        for row in self.list.rows.values():
            assert row.check is not None
            row.check.setEnabled(False)
        self.start_button.setEnabled(False)
        self._total_mb = sum(m.size_mb for m in self._queue)
        self._done_mb = 0
        self.overall.setVisible(True)
        self._downloader.start(list(self._queue))

    def _on_progress(self, model_id: str, fraction: float) -> None:
        model = next(m for m in CATALOG if m.id == model_id)
        row = self.list.rows[model_id]
        row.bar.setVisible(True)
        row.bar.setValue(int(fraction * 100))
        row.status.setText("Henter …")
        done = self._done_mb + fraction * model.size_mb
        self.overall.setValue(int(100 * done / max(1, self._total_mb)))
        self.summary.setText(f"Henter {model.title} …")

    def _on_finished(self, model_id: str, error: str) -> None:
        row = self.list.rows[model_id]
        if error:
            row.status.setText("Fejl")
            QMessageBox.warning(
                self, "Kunne ikke hente", f"{row.model.title} kunne ikke hentes.\n\n{NETWORK_HELP}"
            )
            self.start_button.setEnabled(True)
            self.start_button.setText("Prøv igen")
            return
        row.status.setText("✓ Hentet")
        row.bar.setVisible(False)
        self._installed.add(model_id)
        self._done_mb += row.model.size_mb
        self._queue = [m for m in self._queue if m.id != model_id]
        if not self._queue:
            self._finish()

    def _finish(self) -> None:
        chosen = self.chosen()
        voices = [m for m in chosen if m.kind is Kind.VOICE]
        speech = [m for m in chosen if m.kind is Kind.SPEECH]
        self._cfg.voice = voices[0].source
        if speech:
            if self._cfg.dictation_model not in {m.id for m in speech}:
                self._cfg.dictation_model = speech[0].id
            self._cfg.dictation_enabled = True
        else:
            self._cfg.dictation_enabled = False
        self.basics.apply(self._cfg)
        save_config(self._cfg)
        if self._autostart is not None:
            try:
                self._autostart.set_enabled(self.basics.autostart.isChecked())
            except OSError as exc:
                log.warning("Kunne ikke ændre autostart: %s", exc)
        if sys.platform == "win32":
            from ordhjaelp.ui import tray_help

            try:
                tray_help.request_help_on_start(self.basics.tray_icons.isChecked())
            except OSError as exc:
                log.warning("Kunne ikke huske valget om ikonerne: %s", exc)
        self.accept()

    def reject(self) -> None:  # noqa: D102
        if self._downloader.busy:
            answer = QMessageBox.question(
                self,
                "Afslut?",
                "Der hentes stadig. Vil du afslutte? Hentningen fortsætter næste gang.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().reject()


def needs_first_run(store: ModelStore, cfg: Config) -> bool:
    """Mangler der modeller til det, der er slået til?"""
    from ordhjaelp.models.catalog import get

    voice = next((m for m in of_kind(Kind.VOICE) if m.source == cfg.voice), None)
    if voice is None or not store.is_installed(voice):
        return True
    speech = get(cfg.dictation_model)
    return bool(cfg.dictation_enabled and speech and not store.is_installed(speech))


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
