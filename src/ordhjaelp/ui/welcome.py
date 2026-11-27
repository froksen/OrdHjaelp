"""Velkomstguiden ved første start.

Tre trin:
1. Hvad skal Ordhjælp hjælpe med? Læse op, diktere eller begge dele (alle funktioner).
2. De vigtigste indstillinger til netop det valg.
3. Sprogmodeller: kun det, valget kræver, er sat flueben ved. Resten kan altid hentes
   senere under Indstillinger → Sprogmodeller.

Skifter man senere brug i indstillingerne, og mangler der en model, vises kun trin 3
ved næste start (models_only).
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ordhjaelp.config import (
    MESSAGES_SCREEN,
    MESSAGES_SPEAK,
    USAGE_ALL,
    USAGE_DICTATION,
    USAGE_READ,
    VIEW_TOOLBAR,
    VIEW_TRAY,
    Config,
    save_config,
)
from ordhjaelp.models.catalog import CATALOG, Kind, ModelInfo, of_kind, size_text
from ordhjaelp.models.store import ModelStore
from ordhjaelp.platform.base import Autostart
from ordhjaelp.ui.model_manager import NETWORK_HELP, _Downloader, _ModelList

log = logging.getLogger(__name__)

# Valgene på første side: (brug, overskrift, forklaring med faste linjeskift)
USAGE_CHOICES = (
    (
        USAGE_READ,
        "Læse op",
        "Ordhjælp læser tekst op: det markerede, tekst på skærmen\nog det, du skriver.",
    ),
    (
        USAGE_DICTATION,
        "Diktere",
        "Du taler, og Ordhjælp skriver det, du siger.",
    ),
    (
        USAGE_ALL,
        "Begge dele",
        "Alle funktioner: læse op, diktere og ordforslag, mens du skriver.",
    ),
)
PAGE_USAGE, PAGE_SETTINGS, PAGE_MODELS = range(3)


def _note(text: str) -> QLabel:
    """Grå hjælpetekst. Faste linjeskift (\\n), aldrig setWordWrap."""
    label = QLabel(text)
    label.setStyleSheet("color: gray")
    return label


def _scrolling(content: QWidget) -> QScrollArea:
    """Kan rulles: skole-pc'er med 1366x768 og 125 % har kun ca. 614 punkter i højden."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    return scroll


class FirstRunDialog(QDialog):
    """Velkomstguiden. models_only: kun siden med sprogmodeller (guiden er vist før)."""

    def __init__(
        self,
        store: ModelStore,
        cfg: Config,
        autostart: Autostart | None = None,
        models_only: bool = False,
    ) -> None:
        super().__init__()
        self._store = store
        self._cfg = cfg
        self._autostart = autostart
        self._models_only = models_only
        self._queue: list[ModelInfo] = []
        self._total_mb = 0
        self._done_mb = 0
        self._installed: set[str] = set()
        self.list: _ModelList | None = None
        self.setWindowTitle("Velkommen til Ordhjælp")

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_usage_page())
        self.pages.addWidget(self._build_settings_page())
        self.pages.addWidget(self._build_models_page())

        self.back_button = QPushButton("Tilbage")
        self.back_button.clicked.connect(self._back)
        self.next_button = QPushButton("Næste")
        self.next_button.clicked.connect(self._next)
        self.start_button = QPushButton("Hent og start")
        self.start_button.clicked.connect(self._start)
        self.quit_button = QPushButton("Afslut")
        self.quit_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.quit_button)
        buttons.addStretch()
        buttons.addWidget(self.back_button)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.start_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.pages, 1)
        layout.addLayout(buttons)

        self._downloader = _Downloader(store)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished.connect(self._on_finished)
        self._update_usage_settings()
        self._show_page(PAGE_MODELS if models_only else PAGE_USAGE)
        self._fit_to_screen()

    # -- side 1: hvad skal Ordhjælp hjælpe med? ------------------------------
    def _build_usage_page(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.addWidget(QLabel("<h2>Velkommen til Ordhjælp</h2>"))
        col.addWidget(QLabel("<b>Hvad skal Ordhjælp hjælpe dig med?</b>"))
        col.addWidget(_note("Du kan altid ændre det senere under Indstillinger."))
        self.usage_group = QButtonGroup(self)
        self.usage_buttons: dict[str, QRadioButton] = {}
        for usage, title, explanation in USAGE_CHOICES:
            button = QRadioButton(title)
            font = button.font()
            font.setPointSizeF(font.pointSizeF() * 1.2)
            font.setBold(True)
            button.setFont(font)
            self.usage_group.addButton(button)
            self.usage_buttons[usage] = button
            col.addSpacing(8)
            col.addWidget(button)
            note = _note(explanation)
            note.setContentsMargins(26, 0, 0, 0)  # under teksten, ikke under rundingen
            col.addWidget(note)
        current = self._cfg.usage if self._cfg.welcome_done else USAGE_ALL
        self.usage_buttons.get(current, self.usage_buttons[USAGE_ALL]).setChecked(True)
        self.usage_group.buttonToggled.connect(lambda *_: self._update_usage_settings())
        col.addStretch(1)
        return page

    @property
    def usage(self) -> str:
        for usage, button in self.usage_buttons.items():
            if button.isChecked():
                return usage
        return USAGE_ALL

    # -- side 2: de vigtigste indstillinger -----------------------------------
    def _build_settings_page(self) -> QWidget:
        cfg = self._cfg
        content = QWidget()
        col = QVBoxLayout(content)
        col.addWidget(QLabel("<h2>Indstillinger</h2>"))
        col.addWidget(_note("Det hele kan ændres senere under Indstillinger."))

        # Læs op
        self.reading_box = QGroupBox("Læs op")
        box = QVBoxLayout(self.reading_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Tempo:"))
        row.addWidget(QLabel("Langsom"))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(60, 150)  # samme som i indstillingerne
        self.speed.setSingleStep(5)
        self.speed.setPageStep(10)
        self.speed.setValue(round(cfg.speed * 100))
        row.addWidget(self.speed, 1)
        row.addWidget(QLabel("Hurtig"))
        box.addLayout(row)
        self.read_on_select = QCheckBox("Læs op, så snart der markeres tekst med musen")
        self.read_on_select.setChecked(cfg.read_on_select)
        self.read_at_pointer = QCheckBox("Læs under musen med genveje")
        self.read_at_pointer.setChecked(cfg.read_at_pointer)
        self.read_word = QCheckBox("Læs ordet op, når der trykkes mellemrum")
        self.read_word.setChecked(cfg.read_word_on_space)
        self.read_sentence = QCheckBox("Læs sætningen op ved punktum, ! og ?")
        self.read_sentence.setChecked(cfg.read_sentence_on_period)
        for widget in (
            self.read_on_select,
            self.read_at_pointer,
            self.read_word,
            self.read_sentence,
        ):
            box.addWidget(widget)
        col.addWidget(self.reading_box)

        # Diktering
        self.dictation_box = QGroupBox("Diktering")
        box = QVBoxLayout(self.dictation_box)
        box.addWidget(QLabel('Beskeder (fx "Jeg hørte ikke noget"):'))
        self.messages_screen = QRadioButton("Vis dem på skærmen")
        self.messages_speak = QRadioButton("Læs dem op")
        (self.messages_speak if cfg.speaks_messages else self.messages_screen).setChecked(True)
        box.addWidget(self.messages_screen)
        box.addWidget(self.messages_speak)
        # Har eleven selv valgt? Ellers foreslås skærmen ved kun diktering (så stemmen
        # ikke hentes) og oplæsning ellers (stemmen er der alligevel)
        self._messages_touched = False
        for button in (self.messages_screen, self.messages_speak):
            button.clicked.connect(lambda: setattr(self, "_messages_touched", True))
        self.messages_note = _note("Kun diktering: stemmen hentes kun, hvis\nbeskederne læses op.")
        box.addWidget(self.messages_note)
        col.addWidget(self.dictation_box)

        # Skrivehjælp (kun med alle funktioner)
        self.writing_box = QGroupBox("Mens der skrives")
        box = QVBoxLayout(self.writing_box)
        self.prediction = QCheckBox("Vis ordforslag, mens der skrives")
        self.prediction.setChecked(cfg.prediction_enabled)
        box.addWidget(self.prediction)
        col.addWidget(self.writing_box)

        # Knapper og start
        buttons_box = QGroupBox("Knapper og start")
        box = QVBoxLayout(buttons_box)
        self.view_toolbar = QRadioButton("En lille knaplinje på skærmen")
        self.view_tray = QRadioButton("Et ikon for hver knap ved uret")
        (self.view_tray if cfg.view == VIEW_TRAY else self.view_toolbar).setChecked(True)
        box.addWidget(self.view_toolbar)
        box.addWidget(self.view_tray)
        # Windows 11 gemmer nye ikoner under ^. Kun brugeren kan vise dem, så Ordhjælp
        # viser vejledningen lige efter start. Kun relevant med ikoner ved uret.
        self.tray_icons = QCheckBox("Vis mig, hvordan ikonerne ikke gemmes under ^")
        self.tray_icons.setChecked(True)
        self.tray_icons_how = QPushButton("Se hvordan …")
        self.tray_icons_how.setToolTip("Vejledning: sådan vises ikonerne ved uret")
        self.tray_icons_how.clicked.connect(self._show_tray_help)
        self._tray_row = QWidget()
        trow = QHBoxLayout(self._tray_row)
        trow.setContentsMargins(0, 0, 0, 0)
        trow.addWidget(self.tray_icons)
        trow.addWidget(self.tray_icons_how)
        trow.addStretch()
        box.addWidget(self._tray_row)
        self.view_tray.toggled.connect(self._update_tray_row)
        self._update_tray_row()
        self.autostart = QCheckBox("Start Ordhjælp automatisk, når der logges ind")
        self.autostart.setChecked(self._autostart is not None)
        self.autostart.setVisible(self._autostart is not None)
        box.addWidget(self.autostart)
        col.addWidget(buttons_box)
        col.addStretch(1)
        return _scrolling(content)

    def _update_tray_row(self) -> None:
        self._tray_row.setVisible(self.view_tray.isChecked() and sys.platform == "win32")

    def _update_usage_settings(self) -> None:
        """Vis kun de indstillinger, der hører til det valgte brug."""
        usage = self.usage
        self.reading_box.setVisible(usage != USAGE_DICTATION)
        self.dictation_box.setVisible(usage != USAGE_READ)
        self.writing_box.setVisible(usage == USAGE_ALL)
        self.messages_note.setVisible(usage == USAGE_DICTATION)
        if not self._messages_touched:
            suggested = self.messages_screen if usage == USAGE_DICTATION else self.messages_speak
            suggested.setChecked(True)

    def _show_tray_help(self) -> None:
        from ordhjaelp.platform import open_tray_icon_settings
        from ordhjaelp.ui.tray_help import TrayIconsHelpDialog

        TrayIconsHelpDialog(open_tray_icon_settings, self).exec()

    def collect(self) -> Config:
        """Valgene i guiden lagt ind i en kopi af indstillingerne (uden modellerne)."""
        import copy

        cfg = copy.deepcopy(self._cfg)
        if self._models_only:
            return cfg
        cfg.usage = self.usage
        cfg.messages = MESSAGES_SPEAK if self.messages_speak.isChecked() else MESSAGES_SCREEN
        cfg.speed = self.speed.value() / 100
        cfg.read_on_select = self.read_on_select.isChecked()
        cfg.read_at_pointer = self.read_at_pointer.isChecked()
        cfg.read_word_on_space = self.read_word.isChecked()
        cfg.read_sentence_on_period = self.read_sentence.isChecked()
        cfg.prediction_enabled = self.prediction.isChecked()
        cfg.view = VIEW_TRAY if self.view_tray.isChecked() else VIEW_TOOLBAR
        return cfg

    # -- side 3: sprogmodeller --------------------------------------------------
    def _build_models_page(self) -> QWidget:
        page = QWidget()
        self._models_layout = QVBoxLayout(page)
        self._models_layout.setContentsMargins(0, 0, 0, 0)
        self.models_intro = QLabel()
        self._models_layout.addWidget(self.models_intro)
        self._list_holder = QVBoxLayout()
        self._models_layout.addLayout(self._list_holder, 1)
        self.summary = QLabel()
        self.overall = QProgressBar()
        self.overall.setRange(0, 100)
        self.overall.setVisible(False)
        self._models_layout.addWidget(self.summary)
        self._models_layout.addWidget(self.overall)
        return page

    def _needed_kinds(self, cfg: Config) -> tuple[bool, bool]:
        """(stemme, talegenkendelse): hvad det valgte brug har brug for."""
        speech = cfg.uses_dictation and (cfg.dictation_enabled or not self._models_only)
        return cfg.needs_voice, speech

    def _fill_models(self) -> None:
        """Byg listen ud fra valgene: kun det nødvendige har flueben."""
        cfg = self.collect()
        need_voice, need_speech = self._needed_kinds(cfg)
        kinds = [k for k, need in ((Kind.VOICE, need_voice), (Kind.SPEECH, need_speech)) if need]
        if self.list is not None:
            self.list.setParent(None)
            self.list.deleteLater()
        self.list = _ModelList(choose=True, kinds=kinds)
        self.list.setMinimumHeight(160)
        self._list_holder.addWidget(self.list)
        self._installed = set()
        chosen_speech = cfg.dictation_model
        for row in self.list.rows.values():
            assert row.check is not None
            installed = self._store.is_installed(row.model)
            if installed:
                self._installed.add(row.model.id)
            if row.model.kind is Kind.VOICE:
                wanted = installed or row.model.source == cfg.voice or row.model.recommended
            else:  # én talegenkendelse er nok: den valgte eller den anbefalede
                wanted = installed or row.model.id == chosen_speech
            row.check.setChecked(wanted)
            if installed:
                row.check.setEnabled(False)
                row.status.setText("✓ Hentet")
            row.check.toggled.connect(self._update_summary)
        # Er der kun én stemme og skal den bruges, kan den ikke fravælges
        voices = of_kind(Kind.VOICE)
        if need_voice and len(voices) == 1:
            only = self.list.rows[voices[0].id]
            assert only.check is not None
            only.check.setChecked(True)
            only.check.setEnabled(False)
            if not only.status.text():
                only.status.setText("Påkrævet")
        if self._models_only:
            intro = (
                "<h2>Der mangler sprogmodeller</h2>"
                "Det, du har valgt i indstillingerne, kræver sprogmodeller, som ikke er "
                "hentet.<br>De hentes <b>én gang</b> og virker derefter uden internet."
            )
        else:
            intro = (
                "<h2>Sprogmodeller</h2>"
                "Ordhjælp henter kun det, du har valgt. Det hentes <b>én gang</b> og "
                "virker derefter uden internet.<br>Flere kan altid hentes senere under "
                "<i>Indstillinger → Sprogmodeller</i>."
            )
        self.models_intro.setText(intro)
        self.models_intro.setTextFormat(Qt.TextFormat.RichText)
        self._update_summary()

    def chosen(self, only_missing: bool = False) -> list[ModelInfo]:
        if self.list is None:
            return []
        result = []
        for row in self.list.rows.values():
            assert row.check is not None
            if row.check.isChecked() and not (only_missing and row.model.id in self._installed):
                result.append(row.model)
        return result

    def _update_summary(self) -> None:
        cfg = self.collect()
        chosen = self.chosen()
        missing = self.chosen(only_missing=True)
        has_voice = any(m.kind is Kind.VOICE for m in chosen)
        has_speech = any(m.kind is Kind.SPEECH for m in chosen)
        if cfg.needs_voice and not has_voice:
            problem = "Vælg mindst én stemme."
        elif cfg.usage == USAGE_DICTATION and not has_speech:
            problem = "Vælg mindst én talegenkendelse."
        else:
            problem = ""
        self.start_button.setEnabled(not problem and not self._downloader.busy)
        if problem:
            self.summary.setText(problem)
        elif missing:
            self.summary.setText(f"Der skal hentes {size_text(sum(m.size_mb for m in missing))}.")
            self.start_button.setText("Hent og start")
        else:
            self.summary.setText("Alt er hentet.")
            self.start_button.setText("Start")

    # -- sider og knapper ---------------------------------------------------------
    def _show_page(self, index: int) -> None:
        if index == PAGE_MODELS:
            self._fill_models()
        self.pages.setCurrentIndex(index)
        last = index == PAGE_MODELS
        self.back_button.setVisible(index > PAGE_USAGE and not self._models_only)
        self.next_button.setVisible(not last)
        self.start_button.setVisible(last)
        (self.start_button if last else self.next_button).setDefault(True)

    def _next(self) -> None:
        self._show_page(min(self.pages.currentIndex() + 1, PAGE_MODELS))

    def _back(self) -> None:
        self._show_page(max(self.pages.currentIndex() - 1, PAGE_USAGE))

    def _start(self) -> None:
        if self.pages.currentIndex() != PAGE_MODELS:
            self._show_page(PAGE_MODELS)
        self._queue = self.chosen(only_missing=True)
        if not self._queue:
            self._finish()
            return
        assert self.list is not None
        for row in self.list.rows.values():
            assert row.check is not None
            row.check.setEnabled(False)
        self.start_button.setEnabled(False)
        self.back_button.setEnabled(False)
        self._total_mb = sum(m.size_mb for m in self._queue)
        self._done_mb = 0
        self.overall.setVisible(True)
        self._downloader.start(list(self._queue))

    def _on_progress(self, model_id: str, fraction: float) -> None:
        assert self.list is not None
        model = next(m for m in CATALOG if m.id == model_id)
        row = self.list.rows[model_id]
        row.bar.setVisible(True)
        row.bar.setValue(int(fraction * 100))
        row.status.setText("Henter …")
        done = self._done_mb + fraction * model.size_mb
        self.overall.setValue(int(100 * done / max(1, self._total_mb)))
        self.summary.setText(f"Henter {model.title} …")

    def _on_finished(self, model_id: str, error: str) -> None:
        assert self.list is not None
        row = self.list.rows[model_id]
        if error:
            row.status.setText("Fejl")
            QMessageBox.warning(
                self, "Kunne ikke hente", f"{row.model.title} kunne ikke hentes.\n\n{NETWORK_HELP}"
            )
            self.start_button.setEnabled(True)
            self.start_button.setText("Prøv igen")
            self.back_button.setEnabled(True)
            return
        row.status.setText("✓ Hentet")
        row.bar.setVisible(False)
        self._installed.add(model_id)
        self._done_mb += row.model.size_mb
        self._queue = [m for m in self._queue if m.id != model_id]
        if not self._queue:
            self._finish()

    def _finish(self) -> None:
        new = self.collect()
        chosen = self.chosen()
        voices = [m for m in chosen if m.kind is Kind.VOICE]
        speech = [m for m in chosen if m.kind is Kind.SPEECH]
        if voices:
            new.voice = voices[0].source
        if speech:
            if new.dictation_model not in {m.id for m in speech}:
                new.dictation_model = speech[0].id
            new.dictation_enabled = True
        elif new.uses_dictation:  # ingen talegenkendelse valgt: diktering slås fra
            new.dictation_enabled = False
        new.welcome_done = True
        save_config(new)
        # Ordhjælp starter med det samme med valgene
        self._cfg.__dict__.update(new.__dict__)
        if self._autostart is not None and not self._models_only:
            try:
                self._autostart.set_enabled(self.autostart.isChecked())
            except OSError as exc:
                log.warning("Kunne ikke ændre autostart: %s", exc)
        if sys.platform == "win32" and not self._models_only:
            from ordhjaelp.ui import tray_help

            try:
                tray_help.request_help_on_start(
                    new.view == VIEW_TRAY and self.tray_icons.isChecked()
                )
            except OSError as exc:
                log.warning("Kunne ikke huske valget om ikonerne: %s", exc)
        self.accept()

    def _fit_to_screen(self) -> None:
        """Så højt som indholdet, men aldrig højere end skærmen."""
        size = self.sizeHint()
        size.setWidth(max(size.width(), 560))
        size.setHeight(max(size.height(), 520))
        screen = self.screen()
        if screen is not None:
            size.setHeight(min(size.height(), int(screen.availableGeometry().height() * 0.9)))
        self.resize(size)

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
