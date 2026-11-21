"""Besked, når skrivebordet ikke kan vise ikonerne ved uret (fx GNOME uden udvidelse).

Uden ikonerne kan eleven ikke se, at Ordhjælp kører, og ikke åbne indstillingerne.
GNOME kræver en udvidelse. Beskeden forklarer, hvordan den installeres, og kan
slå den til, hvis den allerede er installeret.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ordhjaelp.config import data_dir
from ordhjaelp.platform.base import TrayExtension
from ordhjaelp.ui.shortcuts import GLOBAL_SHORTCUTS, shortcut_for

HIDE_MARKER = "ikoner-ved-uret-mangler-skjult"  # findes filen, vises beskeden ikke
READY_TIMEOUT = 5.0  # sekunder, vi venter på, at udvidelsen kører
SHOWN_ACTIONS = ("laes", "dikter", "skaerm")


def _marker() -> Path:
    return data_dir() / HIDE_MARKER


def should_show() -> bool:
    return not _marker().exists()


def _remember_hidden() -> None:
    marker = _marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def _rich(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _steps(steps: list[str]) -> QLabel:
    items = "".join(f"<li>{step}</li>" for step in steps)
    return _rich(f"<ol style='margin-left:-20px'>{items}</ol>")


class MissingTrayDialog(QDialog):
    def __init__(
        self,
        extension: TrayExtension,
        hotkeys: dict[str, str] | None = None,
        parent=None,  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        self._extension = extension
        self.enabled = False  # True, når udvidelsen er slået til og kører
        self.setWindowTitle("Ordhjælp – ikonerne ved uret")
        layout = QVBoxLayout(self)
        layout.addWidget(
            _rich(
                "<b>Ordhjælp kører, men ikonerne ved uret kan ikke vises.</b><br>"
                "GNOME viser kun ikoner ved uret med udvidelsen<br>"
                f"<b>{extension.name}</b>."
            )
        )

        state = extension.state()
        self.enable_button: QPushButton | None = None
        if state == "mangler":
            layout.addWidget(
                _steps(
                    [
                        "Installér udvidelsen. Skriv i en terminal:<br>"
                        f"<code>{extension.install_command}</code>",
                        "Log ud, og log ind igen.",
                        "Ordhjælp viser så en knap, der slår udvidelsen til.",
                    ]
                )
            )
        elif state == "slået fra":
            layout.addWidget(QLabel("Udvidelsen er installeret, men slået fra."))
            self.enable_button = QPushButton("Slå ikonerne til")
            self.enable_button.clicked.connect(self._enable)
            layout.addWidget(self.enable_button, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            layout.addWidget(
                QLabel("Udvidelsen er slået til, men kører ikke endnu.\nLog ud, og log ind igen.")
            )

        self.result_label = QLabel()
        self.result_label.hide()
        layout.addWidget(self.result_label)

        keys = [
            (shortcut_for(hotkeys, action), text)
            for action, text in GLOBAL_SHORTCUTS
            if action in SHOWN_ACTIONS and shortcut_for(hotkeys, action)
        ]
        if keys:
            lines = "".join(f"<tr><td><b>{key}</b></td><td>{text}</td></tr>" for key, text in keys)
            layout.addWidget(
                _rich(
                    "Indtil da kan du bruge tastaturgenvejene:"
                    f"<table cellspacing='4'>{lines}</table>"
                )
            )

        self.hide_box = QCheckBox("Vis ikke denne besked igen")
        layout.addWidget(self.hide_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Luk")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _enable(self) -> None:
        assert self.enable_button is not None
        self.enable_button.setEnabled(False)
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok = self._extension.enable() and self._extension.wait_until_ready(READY_TIMEOUT)
        finally:
            QGuiApplication.restoreOverrideCursor()
        if ok:
            self.enabled = True
            self.accept()  # Ordhjælp starter forfra og viser ikonerne
            return
        self.result_label.setText(
            "Udvidelsen kunne ikke startes med det samme.\nLog ud, og log ind igen."
        )
        self.result_label.show()

    def done(self, result: int) -> None:
        if self.hide_box.isChecked():
            _remember_hidden()
        super().done(result)


def explain_missing_tray(extension: TrayExtension, hotkeys: dict[str, str] | None) -> bool:
    """Vis beskeden (hvis den ikke er skjult). True, hvis ikonerne nu kan vises."""
    if not should_show():
        return False
    dialog = MissingTrayDialog(extension, hotkeys)
    dialog.exec()
    return dialog.enabled
