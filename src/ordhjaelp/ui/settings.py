"""Indstillingsvindue (til voksne): tempo, diktering, ikoner og autostart."""

from __future__ import annotations

import copy
import logging
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
    QSlider,
    QVBoxLayout,
)

from ordhjaelp.config import Config, save_config
from ordhjaelp.models.catalog import Kind, of_kind, size_text
from ordhjaelp.models.store import ModelStore
from ordhjaelp.platform.base import Autostart

log = logging.getLogger(__name__)

PREVIEW_TEXT = "Hej! Sådan lyder jeg, når jeg læser op for dig."


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


def needs_restart(old: Config, new: Config) -> bool:
    """Ændringer, der kun kan træde i kraft ved en genstart."""
    return (old.dictation_enabled, old.dictation_model, old.prediction_enabled) != (
        new.dictation_enabled,
        new.dictation_model,
        new.prediction_enabled,
    )


class SettingsDialog(QDialog):
    def __init__(self, hooks: SettingsHooks) -> None:
        super().__init__()
        self._hooks = hooks
        self._original = copy.deepcopy(hooks.config)
        cfg = hooks.config
        self.setWindowTitle("Ordhjælp – indstillinger")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

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
        layout.addWidget(box)

        # -- Diktering --------------------------------------------------
        box = QGroupBox("Diktering")
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

        keys = QLabel("Tastaturgenveje ændres i Systemindstillinger → Tastaturgenveje → Ordhjælp.")
        keys.setWordWrap(True)
        keys.setStyleSheet("color: gray")
        layout.addWidget(keys)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Gem")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annullér")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._speed_changed(self.speed.value())

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

    def _speed_changed(self, value: int) -> None:
        speed = value / 100
        self.speed_label.setText(f"{speed:.2f}".replace(".", ",") + " × normal")
        self._hooks.set_speed(speed)  # så "Prøv stemmen" bruger det nye tempo

    def collect(self) -> Config:
        cfg = copy.deepcopy(self._original)
        cfg.speed = self.speed.value() / 100
        cfg.use_clipboard_fallback = self.clipboard.isChecked()
        cfg.dictation_enabled = self.dictation.isChecked()
        cfg.dictation_model = str(self.model.currentData() or cfg.dictation_model)
        if not self.model.currentData():  # ingen talemodel hentet
            cfg.dictation_enabled = False
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
