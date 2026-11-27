"""Knaplinjens ikoner (SVG) kan tegnes."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp.ui import tray  # noqa: E402


def test_qtsvg_is_loaded_before_icons():
    # I MSIX-pakken finder Qt's SVG-modul kun Qt6Svg.dll, hvis den allerede er indlæst
    assert "PySide6.QtSvg" in sys.modules


def test_icons_are_not_empty():
    _app = QApplication.instance() or QApplication([])
    for name in ("ordhjaelp", "ordhjaelp-stop", "ordhjaelp-pdf", *tray.MIC_ICONS.values()):
        assert not tray._load_icon(name).pixmap(32, 32).isNull(), name
