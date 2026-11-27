"""Oversigt over Ordhjælps tastaturgenveje, så de er lette at finde.

Genvejene læses fra indstillingerne ([genveje] i config.toml), så det, der vises,
altid passer med det, der virker.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ordhjaelp.config import USAGE_ALL, Config

# Rækkefølge og forklaring på genvejene (handling i config.toml → hvad den gør)
GLOBAL_SHORTCUTS: list[tuple[str, str]] = [
    ("laes", "Læs den markerede tekst op"),
    ("stop", "Stop oplæsningen"),
    ("dikter", "Diktér: start, og tryk igen, når du er færdig"),
    ("skaerm", "Læs tekst fra skærmen"),
    ("laes_ord", "Læs ordet under musen"),
    ("laes_saetning", "Læs sætningen under musen"),
    ("laes_herfra", "Læs fra musen og videre"),
]
POINTER_ACTIONS = {"laes_ord", "laes_saetning", "laes_herfra"}

# Mens der vises ordforslag (ens på Linux og Windows)
SUGGESTION_KEYS: list[tuple[str, str]] = [
    ("F1 – F5", "Tag forslag nr. 1–5"),
    ("↓  ↑", "Gå mellem forslagene (ordet læses op)"),
    ("Tab", "Tag det valgte forslag"),
    ("Esc", "Skjul forslagene"),
    ("Højreklik", "Hør et forslag uden at vælge det"),
]

KEY_NAMES = {
    "CTRL": "Ctrl",
    "CONTROL": "Ctrl",
    "ALT": "Alt",
    "SHIFT": "Shift",
    "META": "Win" if sys.platform == "win32" else "Super",
    "SUPER": "Win" if sys.platform == "win32" else "Super",
    "WIN": "Win",
    "SPACE": "Mellemrum",
    "ENTER": "Enter",
    "RETURN": "Enter",
    "ESC": "Esc",
    "ESCAPE": "Esc",
    "PAGEUP": "Page Up",
    "PAGEDOWN": "Page Down",
}


def pretty(trigger: str) -> str:
    """'CTRL+ALT+L' → 'Ctrl+Alt+L' (sådan tasterne står på tastaturet)."""
    parts = [p.strip() for p in trigger.split("+") if p.strip()]
    return "+".join(
        KEY_NAMES.get(p.upper(), p.upper() if len(p) == 1 else p.title()) for p in parts
    )


def shortcut_for(hotkeys: dict[str, str] | None, action: str) -> str:
    """Genvejen til en handling, pænt skrevet ('' hvis der ingen er)."""
    if not hotkeys or not hotkeys.get(action):
        return ""
    return pretty(hotkeys[action])


def with_shortcut(text: str, hotkeys: dict[str, str] | None, action: str) -> str:
    """Menupunkt med genvejen ude til højre (Qt viser teksten efter tab som genvej)."""
    key = shortcut_for(hotkeys, action)
    return f"{text}\t{key}" if key else text


def change_help() -> str:
    if sys.platform == "win32":
        return "Genvejene ændres under [genveje] i indstillingsfilen (config.toml)."
    return "Genvejene ændres i Systemindstillinger → Tastaturgenveje → Ordhjælp."


def _key_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setStyleSheet(
        "QLabel { font-weight: bold; border: 1px solid palette(mid); border-radius: 4px;"
        " padding: 2px 8px; background: palette(base); }"
    )
    return label


def _grid(rows: list[tuple[str, str, bool]]) -> QWidget:
    """Tabel med (tast, forklaring, aktiv)."""
    widget = QWidget()
    grid = QGridLayout(widget)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    for row, (key, text, active) in enumerate(rows):
        key_label = _key_label(key)
        grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignLeft)
        info = QLabel(text)
        if not active:
            info.setStyleSheet("color: gray")
            key_label.setEnabled(False)
        grid.addWidget(info, row, 1)
    grid.setColumnStretch(1, 1)
    return widget


def _belongs_to_usage(cfg: Config, action: str) -> bool:
    """Hører genvejen med til det, Ordhjælp bruges til (kun læs op, kun diktering)?"""
    if action == "dikter":
        return cfg.uses_dictation
    return cfg.uses_reading


class ShortcutsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setWindowTitle("Ordhjælp – genveje")
        layout = QVBoxLayout(self)

        box = QGroupBox("Tastaturgenveje (virker i alle programmer)")
        col = QVBoxLayout(box)
        rows = []
        pointer_off = False
        for action, text in GLOBAL_SHORTCUTS:
            key = shortcut_for(cfg.hotkeys, action)
            if not key or not _belongs_to_usage(cfg, action):
                continue
            active = action not in POINTER_ACTIONS or cfg.read_at_pointer_active
            if not active:
                pointer_off = True
                text += " *"
            rows.append((key, text, active))
        col.addWidget(_grid(rows))
        if pointer_off:
            note = QLabel("* Slå »Læs under musen med genveje« til i indstillingerne.")
            note.setStyleSheet("color: gray")
            col.addWidget(note)
        layout.addWidget(box)

        box = QGroupBox("Når der vises ordforslag")
        col = QVBoxLayout(box)
        col.addWidget(_grid([(key, text, True) for key, text in SUGGESTION_KEYS]))
        box.setVisible(cfg.usage == USAGE_ALL)  # ordforslag hører kun til alle funktioner
        layout.addWidget(box)

        box = QGroupBox("Med musen")
        col = QVBoxLayout(box)
        mouse_rows = [
            ("Klik på ikonet", "Læs den markerede tekst op (klik igen for at stoppe)", True),
            (
                "Dobbeltklik",
                "Læs ordet op, når »Læs ved markering« er slået til",
                cfg.read_on_select_active,
            ),
            (
                "Trippelklik",
                "Læs linjen op, når »Læs ved markering« er slået til",
                cfg.read_on_select_active,
            ),
        ]
        col.addWidget(_grid(mouse_rows))
        box.setVisible(cfg.uses_reading)
        layout.addWidget(box)

        help_label = QLabel(change_help())
        help_label.setStyleSheet("color: gray")
        layout.addWidget(help_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Luk")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
