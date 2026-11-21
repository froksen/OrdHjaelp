"""Indstillingsvindue (til voksne): tempo, diktering, ikoner og autostart."""

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
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ordhjaelp.config import Config, save_config
from ordhjaelp.platform.base import Autostart
from ordhjaelp.stt.whisper_engine import MODEL_CHOICES

log = logging.getLogger(__name__)

PREVIEW_TEXT = "Hej! Sådan lyder jeg, når jeg læser op for dig."
KEYS_HELP_LINUX = "Tastaturgenveje ændres i Systemindstillinger →\nTastaturgenveje → Ordhjælp."
KEYS_HELP_WINDOWS = "Tastaturgenveje ændres under [genveje] i indstillingsfilen (config.toml)."


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
    set_read_on_select: Callable[[bool], None] | None = None


def needs_restart(old: Config, new: Config) -> bool:
    """Ændringer, der kun kan træde i kraft ved en genstart."""
    # Læs under musen bruger genveje, som kun kan registreres ved start
    return (
        old.dictation_enabled,
        old.dictation_model,
        old.prediction_enabled,
        old.read_at_pointer,
    ) != (
        new.dictation_enabled,
        new.dictation_model,
        new.prediction_enabled,
        new.read_at_pointer,
    )


class SettingsDialog(QDialog):
    def __init__(self, hooks: SettingsHooks) -> None:
        super().__init__()
        self._hooks = hooks
        self._original = copy.deepcopy(hooks.config)
        cfg = hooks.config
        self.setWindowTitle("Ordhjælp – indstillinger")
        # Indholdet kan rulles: på en lille skærm (fx 1366x768 med 125 % skalering)
        # er der ikke plads til det hele, og så ville Qt klemme tekst sammen eller skjule den
        content = QWidget()
        layout = QVBoxLayout(content)

        # -- Oplæsning --------------------------------------------------
        box = QGroupBox("Oplæsning")
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
        self.clipboard = QCheckBox("Læs udklipsholderen (Ctrl+C), hvis intet er markeret")
        self.clipboard.setChecked(cfg.use_clipboard_fallback)
        form.addRow(self.clipboard)
        self.read_on_select = QCheckBox("Læs op, så snart der markeres tekst med musen")
        self.read_on_select.setChecked(cfg.read_on_select)
        form.addRow(self.read_on_select)
        note = QLabel("Dobbeltklik læser et ord. Trippelklik læser linjen eller afsnittet.")
        note.setStyleSheet("color: gray")
        form.addRow(note)
        self.read_at_pointer = QCheckBox("Læs under musen med genveje")
        self.read_at_pointer.setChecked(cfg.read_at_pointer)
        form.addRow(self.read_at_pointer)
        # Faste linjeskift, aldrig setWordWrap: en QLabel med automatisk linjeskift
        # får Qt til at gøre vinduet for smalt, så tekst klippes eller forsvinder
        note = QLabel(
            "Peg med musen og tryk Ctrl+Alt+1 (ordet), Ctrl+Alt+2 (sætningen)\n"
            "eller Ctrl+Alt+3 (herfra og videre). Virker fx i Firefox og LibreOffice."
        )
        note.setStyleSheet("color: gray")
        form.addRow(note)
        layout.addWidget(box)

        # -- Diktering --------------------------------------------------
        box = QGroupBox("Diktering")
        form = QFormLayout(box)
        self.dictation = QCheckBox("Slå diktering til")
        self.dictation.setChecked(cfg.dictation_enabled)
        form.addRow(self.dictation)
        self.model = QComboBox()
        for alias, text in MODEL_CHOICES:
            self.model.addItem(text, alias)
        known = [alias for alias, _ in MODEL_CHOICES]
        if cfg.dictation_model not in known:  # selvvalgt model fra filen
            self.model.addItem(cfg.dictation_model, cfg.dictation_model)
        self.model.setCurrentIndex(max(0, self.model.findData(cfg.dictation_model)))
        self.dictation.toggled.connect(self.model.setEnabled)
        self.model.setEnabled(cfg.dictation_enabled)
        form.addRow("Talegenkendelse:", self.model)
        note = QLabel("En ny model hentes automatisk første gang.")
        note.setStyleSheet("color: gray")
        form.addRow("", note)
        layout.addWidget(box)

        # -- Ordforslag ---------------------------------------------------
        box = QGroupBox("Mens der skrives")
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
        note = QLabel("Kræver at IBus er valgt som indtastningsmetode (se vejledningen).")
        note.setStyleSheet("color: gray")
        col.addWidget(note)
        layout.addWidget(box)

        # -- Ikoner og start --------------------------------------------
        box = QGroupBox("Ikoner ved uret")
        col = QVBoxLayout(box)
        self.icon_mic = QCheckBox("Mikrofon (diktering)")
        self.icon_mic.setChecked(cfg.show_icons.get("dikter", True))
        self.icon_screen = QCheckBox("Læs fra skærmen")
        self.icon_screen.setChecked(cfg.show_icons.get("skaerm", True))
        col.addWidget(self.icon_mic)
        col.addWidget(self.icon_screen)
        info = QLabel("Det blå ikon (læs op) vises altid – her ligger også denne menu.")
        info.setStyleSheet("color: gray")
        col.addWidget(info)
        layout.addWidget(box)

        self.autostart = QCheckBox("Start Ordhjælp automatisk, når der logges ind")
        if hooks.autostart is None:
            self.autostart.setEnabled(False)
        else:
            self.autostart.setChecked(hooks.autostart.is_enabled())
        layout.addWidget(self.autostart)

        keys = QLabel(KEYS_HELP_WINDOWS if sys.platform == "win32" else KEYS_HELP_LINUX)
        keys.setStyleSheet("color: gray")
        layout.addWidget(keys)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Gem")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annullér")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        scrollbar = scroll.verticalScrollBar().sizeHint().width()
        scroll.setMinimumWidth(max(480, content.sizeHint().width()) + scrollbar)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll, 1)
        bottom = QVBoxLayout()
        bottom.setContentsMargins(11, 0, 11, 11)
        bottom.addWidget(buttons)
        outer.addLayout(bottom)
        self._content = content
        self._scroll = scroll
        self._bottom = bottom
        self._outer = outer
        self._fit_to_screen()
        self._speed_changed(self.speed.value())

    def _fit_to_screen(self) -> None:
        """Så højt som indholdet, men aldrig højere end skærmen."""
        wanted = (
            self._content.sizeHint().height()
            + self._outer.spacing()
            + self._bottom.sizeHint().height()
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
        cfg.speed = self.speed.value() / 100
        cfg.use_clipboard_fallback = self.clipboard.isChecked()
        cfg.read_on_select = self.read_on_select.isChecked()
        cfg.read_at_pointer = self.read_at_pointer.isChecked()
        cfg.dictation_enabled = self.dictation.isChecked()
        cfg.dictation_model = str(self.model.currentData())
        cfg.prediction_enabled = self.prediction.isChecked()
        cfg.read_word_on_space = self.read_word.isChecked()
        cfg.read_sentence_on_period = self.read_sentence.isChecked()
        cfg.show_icons["dikter"] = self.icon_mic.isChecked()
        cfg.show_icons["skaerm"] = self.icon_screen.isChecked()
        return cfg

    def accept(self) -> None:  # noqa: D102
        new = self.collect()
        hooks = self._hooks
        save_config(new)
        hooks.set_clipboard_fallback(new.use_clipboard_fallback)
        if hooks.set_read_on_select is not None:
            hooks.set_read_on_select(new.read_on_select)
        for name in ("dikter", "skaerm"):
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
            log.info("Genstarter for at skifte talegenkendelse")
            hooks.restart()

    def reject(self) -> None:  # noqa: D102
        self._hooks.set_speed(self._original.speed)  # fortryd forhåndsvisning
        super().reject()
