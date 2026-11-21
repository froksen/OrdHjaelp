"""Vejledning: vis Ordhjælps ikoner ved uret på Windows 11.

Windows 11 gemmer nye ikoner under ^ ved uret. Kun brugeren kan vælge, at de skal
vises. Windows tillader ikke, at et program gør det selv (det blev afprøvet:
Windows' gemte valg i registreringsdatabasen bliver ikke læst igen). Derfor
viser Ordhjælp, hvordan man gør, og kan åbne Windows' egen indstilling.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ordhjaelp.config import data_dir

# Findes filen, er beskeden ved første start allerede vist
SHOWN_MARKER = "ikoner-ved-uret-vist"

TIP_TITLE = "Ordhjælp kører"
TIP_TEXT = (
    "Ordhjælps ikoner ligger måske under ^ ved uret.\nKlik her for at se, hvordan de altid vises."
)

DRAG_STEPS = [
    "Klik på <b>^</b> ved uret.",
    "Træk Ordhjælps ikoner ned på proceslinjen ved siden af uret.",
]
SETTINGS_STEPS = [
    "Klik på <b>Åbn Windows' indstillinger</b> herunder.",
    "Åbn <b>Andre ikoner på proceslinjen</b>.",
    "Slå Ordhjælp til. Kører Ordhjælp fra kildekoden, hedder den "
    "<b>pythonw.exe</b> eller <b>Python</b> på listen.",
]


def first_run_marker() -> Path:
    return data_dir() / SHOWN_MARKER


def should_show_first_run_tip() -> bool:
    return not first_run_marker().exists()


def remember_first_run_tip() -> None:
    marker = first_run_marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def _steps(steps: list[str]) -> QLabel:
    items = "".join(f"<li>{step}</li>" for step in steps)
    label = QLabel(f"<ol style='margin-left:-20px'>{items}</ol>")
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


class TrayIconsHelpDialog(QDialog):
    def __init__(self, open_settings, parent=None) -> None:  # noqa: ANN001
        """:param open_settings: åbner Windows' indstillinger; False, hvis det ikke lykkedes."""
        super().__init__(parent)
        self._open_settings = open_settings
        self.setWindowTitle("Ordhjælp – ikonerne ved uret")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Windows gemmer nye ikoner under <b>^</b> ved uret.<br>"
                "Sådan bliver Ordhjælps ikoner altid synlige:"
            )
        )

        box = QGroupBox("Den hurtige måde")
        col = QVBoxLayout(box)
        col.addWidget(_steps(DRAG_STEPS))
        layout.addWidget(box)

        box = QGroupBox("Eller i Windows' indstillinger")
        col = QVBoxLayout(box)
        col.addWidget(_steps(SETTINGS_STEPS))
        button = QPushButton("Åbn Windows' indstillinger")
        button.clicked.connect(self._open)
        col.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        self.open_failed = QLabel(
            "Kunne ikke åbne indstillingerne. Højreklik på proceslinjen,\n"
            "og vælg Indstillinger for proceslinjen."
        )
        self.open_failed.setStyleSheet("color: gray")
        self.open_failed.hide()
        col.addWidget(self.open_failed)
        layout.addWidget(box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Luk")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open(self) -> None:
        self.open_failed.setVisible(not self._open_settings())
