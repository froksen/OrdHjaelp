"""Indstillingsvindue (til voksne) i faner: brug, læs op, skriv, knapper, start og genveje."""

from __future__ import annotations

import copy
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QTabWidget,
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
from ordhjaelp.models.catalog import Kind, of_kind, size_text
from ordhjaelp.models.store import ModelStore
from ordhjaelp.platform.base import Autostart, TypingSetup
from ordhjaelp.ui.shortcuts import POINTER_ACTIONS, shortcut_for
from ordhjaelp.ui.typing_setup import OK_COLOR, TypingSetupDialog, all_ok, summary

log = logging.getLogger(__name__)

PREVIEW_TEXT = "Hej! Sådan lyder jeg, når jeg læser op for dig."
KEYS_HELP_LINUX = "Tastaturgenveje ændres i Systemindstillinger →\nTastaturgenveje → Ordhjælp."
KEYS_HELP_WINDOWS = "Tastaturgenveje ændres under [genveje]\ni indstillingsfilen (config.toml)."


def _note(text: str) -> QLabel:
    """Grå hjælpetekst. Brug faste linjeskift (\\n), aldrig setWordWrap."""
    label = QLabel(text)
    label.setStyleSheet("color: gray")
    return label


@dataclass
class SettingsHooks:
    """Det, indstillingsvinduet må ændre i det kørende program."""

    config: Config
    set_speed: Callable[[float], None]
    say: Callable[[str], object]
    set_clipboard_fallback: Callable[[bool], None]
    set_icon_visible: Callable[[str, bool], None]
    restart: Callable[[], None]
    autostart: Autostart | None = None
    models: ModelStore | None = None
    set_read_on_select: Callable[[bool], None] | None = None
    typing_setup: TypingSetup | None = None
    set_pdf_ocr: Callable[[bool], None] | None = None
    set_view: Callable[[str], None] | None = None  # knaplinje eller ikoner ved uret


def needs_restart(old: Config, new: Config) -> bool:
    """Ændringer, der kun kan træde i kraft ved en genstart."""

    # Læs under musen bruger genveje, som kun kan registreres ved start. Et andet brug
    # (kun læs op, kun diktering) ændrer knapper, genveje og måske hvilke modeller der
    # skal hentes: det sker ved start.
    def started_with(cfg: Config) -> tuple:
        return (
            cfg.usage,
            cfg.needs_voice,
            cfg.dictation_active,
            cfg.dictation_model,
            cfg.typing_help_enabled,
            cfg.read_at_pointer_active,
        )

    return started_with(old) != started_with(new)


class SettingsDialog(QDialog):
    def __init__(self, hooks: SettingsHooks) -> None:
        super().__init__()
        self._hooks = hooks
        self._original = copy.deepcopy(hooks.config)
        cfg = hooks.config
        self.setWindowTitle("Ordhjælp – indstillinger")
        # Fire faner, så der ikke er så meget at se på ad gangen. Hver fane kan rulles:
        # på en lille skærm (fx 1366x768 med 125 % skalering) er der ikke plads til
        # det hele, og så ville Qt klemme tekst sammen eller skjule den
        self._tabs = QTabWidget()
        self._pages: list[tuple[QScrollArea, QWidget]] = []

        # == Fane: Brug ====================================================
        layout = self._add_page("Brug")
        box = QGroupBox("Hvad skal Ordhjælp hjælpe med?")
        col = QVBoxLayout(box)
        self.usage_buttons: dict[str, QRadioButton] = {}
        for usage, title, explanation in (
            (USAGE_READ, "Læse op", "Læs op, læs fra skærmen, PDF og læs mens du skriver."),
            (USAGE_DICTATION, "Diktere", "Kun mikrofonen: tal, og Ordhjælp skriver."),
            (USAGE_ALL, "Begge dele", "Alle funktioner, også ordforslag."),
        ):
            button = QRadioButton(title)
            self.usage_buttons[usage] = button
            col.addWidget(button)
            col.addWidget(_note(explanation))
        self.usage_buttons.get(cfg.usage, self.usage_buttons[USAGE_ALL]).setChecked(True)
        col.addWidget(
            _note(
                "Det fravalgte bliver gemt og kommer igen, hvis du vælger det igen.\n"
                "Mangler der en sprogmodel, spørger Ordhjælp, når den starter igen."
            )
        )
        layout.addWidget(box)

        self.messages_box = QGroupBox("Beskeder fra diktering")
        col = QVBoxLayout(self.messages_box)
        col.addWidget(_note('Fx "Jeg hørte ikke noget".'))
        self.messages_screen = QRadioButton("Vis dem på skærmen")
        self.messages_speak = QRadioButton("Læs dem op (kræver stemmen)")
        (self.messages_speak if cfg.speaks_messages else self.messages_screen).setChecked(True)
        col.addWidget(self.messages_screen)
        col.addWidget(self.messages_speak)
        layout.addWidget(self.messages_box)

        # == Fane: Læs op ==================================================
        layout = self._add_page("Læs op")
        box = QGroupBox("Stemme")
        form = QFormLayout(box)
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(60, 150)  # 0,60 – 1,50
        self.speed.setSingleStep(5)
        self.speed.setPageStep(10)
        self.speed.setValue(round(cfg.speed * 100))
        self.speed_label = QLabel()
        self.speed.valueChanged.connect(self._speed_changed)
        row = QHBoxLayout()
        row.addWidget(QLabel("Langsom"))
        row.addWidget(self.speed, 1)
        row.addWidget(QLabel("Hurtig"))
        form.addRow("Tempo:", row)
        preview = QPushButton("▶  Prøv stemmen")
        preview.clicked.connect(lambda: hooks.say(PREVIEW_TEXT))
        prow = QHBoxLayout()
        prow.addWidget(self.speed_label)
        prow.addStretch()
        prow.addWidget(preview)
        form.addRow("", prow)
        layout.addWidget(box)

        box = QGroupBox("Andre måder at få læst op")
        col = QVBoxLayout(box)
        self.read_on_select = QCheckBox("Læs op, så snart der markeres tekst med musen")
        self.read_on_select.setChecked(cfg.read_on_select)
        col.addWidget(self.read_on_select)
        col.addWidget(_note("Dobbeltklik læser et ord. Trippelklik læser linjen eller afsnittet."))
        self.read_at_pointer = QCheckBox("Læs under musen med genveje")
        self.read_at_pointer.setChecked(cfg.read_at_pointer)
        col.addWidget(self.read_at_pointer)
        # Faste linjeskift, aldrig setWordWrap: en QLabel med automatisk linjeskift
        # får Qt til at gøre vinduet for smalt, så tekst klippes eller forsvinder
        keys = {a: shortcut_for(cfg.hotkeys, a) for a in POINTER_ACTIONS}
        col.addWidget(
            _note(
                f"Peg med musen og tryk {keys['laes_ord']} (ordet), {keys['laes_saetning']} "
                f"(sætningen)\neller {keys['laes_herfra']} (herfra og videre). Virker fx i "
                + (
                    "Word, Edge og Notesblok."
                    if sys.platform == "win32"
                    else "Firefox og LibreOffice."
                )
            )
        )
        self.clipboard = QCheckBox("Læs udklipsholderen (Ctrl+C), hvis intet er markeret")
        self.clipboard.setChecked(cfg.use_clipboard_fallback)
        col.addWidget(self.clipboard)
        layout.addWidget(box)

        # == Fane: Skriv ===================================================
        layout = self._add_page("Skriv")
        box = QGroupBox("Diktering")
        self.dictation_box = box
        form = QFormLayout(box)
        self.dictation = QCheckBox("Slå diktering til")
        self.dictation.setChecked(cfg.dictation_enabled)
        form.addRow(self.dictation)
        self.model = QComboBox()
        self._fill_models(cfg.dictation_model)
        self.dictation.toggled.connect(self._update_model_enabled)
        manage = QPushButton("Sprogmodeller …")
        manage.setToolTip("Hent flere stemmer og talemodeller, eller slet dem")
        manage.clicked.connect(self._open_model_manager)
        manage.setEnabled(hooks.models is not None)
        mrow = QHBoxLayout()
        mrow.addWidget(self.model, 1)
        mrow.addWidget(manage)
        form.addRow("Talegenkendelse:", mrow)
        self._update_model_enabled()
        layout.addWidget(box)

        box = QGroupBox("Mens der skrives")
        self.typing_box = box
        col = QVBoxLayout(box)
        self.prediction = QCheckBox("Vis ordforslag, mens der skrives")
        self.prediction.setChecked(cfg.prediction_enabled)
        col.addWidget(self.prediction)
        self.read_word = QCheckBox("Læs ordet op, når der trykkes mellemrum")
        self.read_word.setChecked(cfg.read_word_on_space)
        col.addWidget(self.read_word)
        self.read_sentence = QCheckBox("Læs sætningen op ved punktum, ! og ?")
        self.read_sentence.setChecked(cfg.read_sentence_on_period)
        col.addWidget(self.read_sentence)
        self._add_typing_status(col)
        layout.addWidget(box)

        # == Fane: Knapper =================================================
        layout = self._add_page("Knapper")
        box = QGroupBox("Hvor knapperne vises")
        col = QVBoxLayout(box)
        self.view_toolbar = QRadioButton("En lille knaplinje på skærmen")
        self.view_tray = QRadioButton("Et ikon for hver knap ved uret")
        (self.view_tray if cfg.view == VIEW_TRAY else self.view_toolbar).setChecked(True)
        col.addWidget(self.view_toolbar)
        col.addWidget(self.view_tray)
        col.addWidget(
            _note(
                "Knaplinjen kan flyttes, og den kan foldes ind med ‹.\n"
                "Med knaplinjen vises intet ved uret. Menuen ligger under ⋯."
            )
        )
        # Windows 11 gemmer nye ikoner under ^. Kun brugeren kan vælge at vise dem.
        self.tray_help = QPushButton("Vis ikonerne ved uret …")
        self.tray_help.setToolTip("Sådan bliver ikonerne synlige i stedet for gemt under ^")
        self.tray_help.clicked.connect(self._open_tray_help)
        self.view_tray.toggled.connect(
            lambda on: self.tray_help.setVisible(on and sys.platform == "win32")
        )
        self.tray_help.setVisible(self.view_tray.isChecked() and sys.platform == "win32")
        col.addWidget(self.tray_help, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(box)

        box = QGroupBox("Vis disse knapper ud over læs op")
        col = QVBoxLayout(box)
        self.icon_mic = QCheckBox("Mikrofon (diktering)")
        self.icon_mic.setChecked(cfg.show_icons.get("dikter", True))
        self.icon_screen = QCheckBox("Læs fra skærmen")
        self.icon_screen.setChecked(cfg.show_icons.get("skaerm", True))
        self.icon_pdf = QCheckBox("Gør en PDF søgbar")
        self.icon_pdf.setChecked(cfg.show_icons.get("pdf", True))
        col.addWidget(self.icon_mic)
        col.addWidget(self.icon_screen)
        col.addWidget(self.icon_pdf)
        self.pdf_ocr = QCheckBox('Vis også "Gør en PDF søgbar" i menuen')
        self.pdf_ocr.setChecked(cfg.pdf_ocr_enabled)
        col.addWidget(self.pdf_ocr)
        self._pdf_note = _note(
            "Gør en PDF søgbar laver en kopi af en scannet PDF, hvor teksten\n"
            "kan markeres og læses op. Den gamle PDF bliver ikke ændret."
        )
        col.addWidget(self._pdf_note)
        layout.addWidget(box)

        # == Fane: Start og genveje ========================================
        layout = self._add_page("Start og genveje")
        box = QGroupBox("Start")
        col = QVBoxLayout(box)
        self.autostart = QCheckBox("Start Ordhjælp automatisk, når der logges ind")
        if hooks.autostart is None:
            self.autostart.setEnabled(False)
        else:
            self.autostart.setChecked(hooks.autostart.is_enabled())
        col.addWidget(self.autostart)
        layout.addWidget(box)

        box = QGroupBox("Tastaturgenveje")
        col = QVBoxLayout(box)
        col.addWidget(_note(KEYS_HELP_WINDOWS if sys.platform == "win32" else KEYS_HELP_LINUX))
        show_keys = QPushButton("Vis alle genveje …")
        show_keys.setToolTip("Oversigt over alle genveje og tasterne til ordforslag")
        show_keys.clicked.connect(self._open_shortcuts)
        col.addWidget(show_keys, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(box)

        for _, content in self._pages:
            content.layout().addStretch(1)  # grupperne øverst, ikke spredt ud
        widest = max(content.sizeHint().width() for _, content in self._pages)
        for scroll, _ in self._pages:
            scrollbar = scroll.verticalScrollBar().sizeHint().width()
            scroll.setMinimumWidth(max(480, widest) + scrollbar)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Gem")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annullér")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer = QVBoxLayout(self)
        outer.addWidget(self._tabs, 1)
        outer.addWidget(buttons)
        self._outer = outer
        self._buttons = buttons
        self._fit_to_screen()
        self._speed_changed(self.speed.value())
        for button in self.usage_buttons.values():
            button.toggled.connect(self._update_usage)
        self._update_usage()

    # -- brug: kun læs op, kun diktering eller alle funktioner -------------------
    @property
    def usage(self) -> str:
        for usage, button in self.usage_buttons.items():
            if button.isChecked():
                return usage
        return USAGE_ALL

    def _update_usage(self) -> None:
        """Vis kun det, der hører til det valgte brug."""
        usage = self.usage
        reading = usage != USAGE_DICTATION
        dictating = usage != USAGE_READ
        self._tabs.setTabVisible(1, reading)  # Læs op
        self.messages_box.setVisible(dictating)
        self.dictation_box.setVisible(dictating)
        self.prediction.setVisible(usage == USAGE_ALL)
        self.read_word.setVisible(reading)
        self.read_sentence.setVisible(reading)
        self.typing_box.setVisible(reading or usage == USAGE_ALL)
        self.icon_mic.setVisible(dictating)
        for widget in (self.icon_screen, self.icon_pdf, self.pdf_ocr, self._pdf_note):
            widget.setVisible(reading)
        if hasattr(self, "_typing_row"):
            self._update_typing_status()

    def _add_page(self, title: str) -> QVBoxLayout:
        """En ny fane, der kan rulles. Returnerer layoutet, som grupperne lægges i."""
        content = QWidget()
        layout = QVBoxLayout(content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        self._tabs.addTab(scroll, title)
        self._pages.append((scroll, content))
        return layout

    # -- ordforslag: er systemet sat op (IBus på Linux)? ---------------------
    def _add_typing_status(self, col: QVBoxLayout) -> None:
        self._typing_boxes = (self.prediction, self.read_word, self.read_sentence)
        setup = self._hooks.typing_setup
        if setup is None:  # fx macOS: findes endnu ikke
            note = QLabel("Ordforslag og læs mens du skriver findes endnu ikke her.")
            note.setStyleSheet("color: gray")
            col.addWidget(note)
            return
        self.typing_status = QLabel()
        help_button = QPushButton("Hjælp til opsætning …")
        help_button.setToolTip("Vejledning og tjek af, om ordforslag er sat op")
        help_button.clicked.connect(self._open_typing_setup)
        self._typing_row = QWidget()
        row = QHBoxLayout(self._typing_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.typing_status, 1)
        row.addWidget(help_button)
        col.addWidget(self._typing_row)
        for box in self._typing_boxes:
            box.toggled.connect(self._update_typing_status)
        self._update_typing_status()

    def _update_typing_status(self) -> None:
        setup = self._hooks.typing_setup
        # Kun det, der hører til det valgte brug (fanen kan være skjult, så ikke isVisible)
        usage = self.usage if hasattr(self, "usage_buttons") else USAGE_ALL
        allowed = {
            self.prediction: usage == USAGE_ALL,
            self.read_word: usage != USAGE_DICTATION,
            self.read_sentence: usage != USAGE_DICTATION,
        }
        wanted = any(box.isChecked() and allowed[box] for box in self._typing_boxes)
        self._typing_row.setVisible(wanted)
        if setup is None or not wanted:
            return
        checks = setup.checks()
        if not all_ok(checks) and all_ok(checks[:-1]) and not self._original.typing_help_enabled:
            # Alt er sat op – Ordhjælp kobler sig først på (IBus/tastaturet), når der gemmes
            text, color = "✔ Klar – virker, når du gemmer", OK_COLOR
        else:
            text, color = summary(checks)
        self.typing_status.setText(text)
        self.typing_status.setStyleSheet(f"color: {color}")

    def _open_shortcuts(self) -> None:
        from ordhjaelp.ui.shortcuts import ShortcutsDialog

        ShortcutsDialog(self.collect(), self).exec()

    def _open_tray_help(self) -> None:
        from ordhjaelp.platform import open_tray_icon_settings
        from ordhjaelp.ui.tray_help import TrayIconsHelpDialog

        TrayIconsHelpDialog(open_tray_icon_settings, self).exec()

    def _open_typing_setup(self) -> None:
        assert self._hooks.typing_setup is not None
        TypingSetupDialog(self._hooks.typing_setup, self).exec()
        self._update_typing_status()

    def _fill_models(self, selected: str) -> None:
        """Kun hentede talemodeller kan vælges."""
        store = self._hooks.models
        self.model.clear()
        for model in of_kind(Kind.SPEECH):
            if store is None or store.is_installed(model):
                self.model.addItem(f"{model.title} ({size_text(model.size_mb)})", model.id)
        if selected and self.model.findData(selected) < 0 and store is None:
            self.model.addItem(selected, selected)  # selvvalgt model fra filen
        if self.model.count() == 0:
            self.model.addItem("Ingen hentet – klik på Sprogmodeller …", "")
        self.model.setCurrentIndex(max(0, self.model.findData(selected)))

    def _update_model_enabled(self) -> None:
        self.model.setEnabled(self.dictation.isChecked() and bool(self.model.currentData()))

    def _open_model_manager(self) -> None:
        from ordhjaelp.ui.model_manager import ModelManagerDialog

        assert self._hooks.models is not None
        current = str(self.model.currentData() or "")
        dialog = ModelManagerDialog(self._hooks.models, self._hooks.config)
        dialog.exec()
        self._fill_models(current)
        self._update_model_enabled()

    def _fit_to_screen(self) -> None:
        """Så højt som den højeste fane, men aldrig højere end skærmen."""
        tallest = max(content.sizeHint().height() for _, content in self._pages)
        tab_bar = self._tabs.tabBar().sizeHint().height()
        margins = self._outer.contentsMargins()
        wanted = (
            tallest
            + tab_bar
            + 8  # fanens kant
            + self._outer.spacing()
            + self._buttons.sizeHint().height()
            + margins.top()
            + margins.bottom()
        )
        screen = self.screen()
        if screen is not None:
            wanted = min(wanted, int(screen.availableGeometry().height() * 0.9))
        self.resize(self.minimumSizeHint().width(), wanted)

    def _speed_changed(self, value: int) -> None:
        speed = value / 100
        self.speed_label.setText(f"{speed:.2f}".replace(".", ",") + " × normal")
        self._hooks.set_speed(speed)  # så "Prøv stemmen" bruger det nye tempo

    def collect(self) -> Config:
        cfg = copy.deepcopy(self._original)
        cfg.usage = self.usage
        cfg.messages = MESSAGES_SPEAK if self.messages_speak.isChecked() else MESSAGES_SCREEN
        cfg.speed = self.speed.value() / 100
        cfg.use_clipboard_fallback = self.clipboard.isChecked()
        cfg.read_on_select = self.read_on_select.isChecked()
        cfg.read_at_pointer = self.read_at_pointer.isChecked()
        cfg.dictation_enabled = self.dictation.isChecked()
        cfg.dictation_model = str(self.model.currentData() or cfg.dictation_model)
        # Ingen talemodel hentet: diktering forbliver valgt, og Ordhjælp spørger, om
        # modellen skal hentes, når den starter igen (velkomstguidens side med modeller)
        cfg.prediction_enabled = self.prediction.isChecked()
        cfg.read_word_on_space = self.read_word.isChecked()
        cfg.read_sentence_on_period = self.read_sentence.isChecked()
        cfg.pdf_ocr_enabled = self.pdf_ocr.isChecked()
        cfg.show_icons["dikter"] = self.icon_mic.isChecked()
        cfg.show_icons["skaerm"] = self.icon_screen.isChecked()
        cfg.show_icons["pdf"] = self.icon_pdf.isChecked()
        cfg.view = VIEW_TRAY if self.view_tray.isChecked() else VIEW_TOOLBAR
        return cfg

    def accept(self) -> None:  # noqa: D102
        new = self.collect()
        hooks = self._hooks
        save_config(new)
        hooks.set_clipboard_fallback(new.use_clipboard_fallback)
        if hooks.set_read_on_select is not None:
            hooks.set_read_on_select(new.read_on_select_active)
        if hooks.set_pdf_ocr is not None:
            hooks.set_pdf_ocr(new.pdf_ocr_enabled)  # skjules af knaplinjen ved kun diktering
        hooks.config.view = new.view  # set_icon_visible ser på den valgte visning
        if hooks.set_view is not None and new.view != self._original.view:
            hooks.set_view(new.view)
        for name in ("dikter", "skaerm", "pdf"):
            hooks.set_icon_visible(name, new.show_icons[name])
        if hooks.autostart is not None and self.autostart.isEnabled():
            try:
                hooks.autostart.set_enabled(self.autostart.isChecked())
            except OSError:
                log.exception("Kunne ikke ændre autostart")
        restart = needs_restart(self._original, new)
        hooks.config.__dict__.update(copy.deepcopy(new).__dict__)
        super().accept()
        if restart:
            log.info("Genstarter med de nye indstillinger")
            hooks.restart()

    def reject(self) -> None:  # noqa: D102
        self._hooks.set_speed(self._original.speed)  # fortryd forhåndsvisning
        super().reject()
