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
from ordhjaelp.platform.base import Autostart
from ordhjaelp.stt.whisper_engine import MODEL_CHOICES

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


def needs_restart(old: Config, new: Config) -> bool:
    """Ændringer, der kun kan træde i kraft ved en genstart."""
    return (old.dictation_enabled, old.dictation_model) != (
        new.dictation_enabled,
        new.dictation_model,
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

    def _speed_changed(self, value: int) -> None:
        speed = value / 100
        self.speed_label.setText(f"{speed:.2f}".replace(".", ",") + " × normal")
        self._hooks.set_speed(speed)  # så "Prøv stemmen" bruger det nye tempo

    def collect(self) -> Config:
        cfg = copy.deepcopy(self._original)
        cfg.speed = self.speed.value() / 100
        cfg.use_clipboard_fallback = self.clipboard.isChecked()
        cfg.dictation_enabled = self.dictation.isChecked()
        cfg.dictation_model = str(self.model.currentData())
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
