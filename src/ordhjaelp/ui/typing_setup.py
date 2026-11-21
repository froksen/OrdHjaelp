"""Vejledning og tjek: er systemet sat op til ordforslag og læs mens du skriver?"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ordhjaelp.platform.base import SetupCheck, TypingSetup

OK_COLOR = "#2e7d32"
PROBLEM_COLOR = "#c62828"


def all_ok(checks: list[SetupCheck]) -> bool:
    return all(check.ok for check in checks)


def summary(checks: list[SetupCheck]) -> tuple[str, str]:
    """Kort status til indstillingsvinduet: (tekst, farve)."""
    if all_ok(checks):
        return "✔ Klar – alt er sat op", OK_COLOR
    return "✘ Mangler opsætning", PROBLEM_COLOR


def checks_html(checks: list[SetupCheck]) -> str:
    rows = []
    first_problem = True
    for check in checks:
        if check.ok:
            rows.append(f'<span style="color:{OK_COLOR}">✔</span> {check.label}')
            continue
        row = f'<span style="color:{PROBLEM_COLOR}">✘</span> {check.label}'
        if first_problem and check.fix:  # kun det første problem – resten følger ofte af det
            row += f'<br><span style="color:gray">&nbsp;&nbsp;&nbsp;&nbsp;{check.fix}</span>'
            first_problem = False
        rows.append(row)
    return "<br>".join(rows)


class TypingSetupDialog(QDialog):
    def __init__(self, setup: TypingSetup, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._setup = setup
        self.setWindowTitle("Ordhjælp – opsætning af ordforslag")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Ordforslag og læs mens du skriver bruger <b>IBus</b>, som er Linux' "
            "system til indtastning. Det skal slås til én gang."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        box = QGroupBox("Sådan gør du")
        col = QVBoxLayout(box)
        steps = "".join(f"<li>{step}</li>" for step in setup.guide())
        guide = QLabel(f"<ol style='margin-left:-20px'>{steps}</ol>")
        guide.setWordWrap(True)
        guide.setTextFormat(Qt.TextFormat.RichText)
        col.addWidget(guide)
        open_button = QPushButton("Åbn tastaturindstillingerne")
        open_button.clicked.connect(self._open_settings)
        self._open_failed = QLabel(
            "Kunne ikke åbne indstillingerne. Find dem i Systemindstillinger."
        )
        self._open_failed.setStyleSheet("color: gray")
        self._open_failed.setWordWrap(True)
        self._open_failed.hide()
        col.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self._open_failed)
        layout.addWidget(box)

        box = QGroupBox("Status")
        col = QVBoxLayout(box)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.RichText)
        self.status.setWordWrap(True)
        col.addWidget(self.status)
        recheck = QPushButton("Tjek igen")
        recheck.clicked.connect(self.refresh)
        row = QHBoxLayout()
        row.addWidget(recheck)
        row.addStretch()
        col.addLayout(row)
        layout.addWidget(box)

        layout.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Luk")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.status.setText(checks_html(self._setup.checks()))

    def _open_settings(self) -> None:
        self._open_failed.setVisible(not self._setup.open_settings())
