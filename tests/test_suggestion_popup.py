"""Forslagsvinduet ved markøren."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint, QRect  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp.ui.suggestions import SuggestionPopup, place_below  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_placed_below_caret() -> None:
    screen = QRect(0, 0, 1000, 700)
    assert place_below(QPoint(100, 200), 18, QRect(0, 0, 150, 120), screen) == QPoint(100, 222)


def test_placed_above_caret_at_bottom_and_kept_on_screen() -> None:
    screen = QRect(0, 0, 1000, 700)
    pos = place_below(QPoint(950, 650), 18, QRect(0, 0, 150, 120), screen)
    assert pos == QPoint(1000 - 150 - 1, 650 - 120 - 4)


def test_shows_numbered_suggestions_and_marks_choice(app) -> None:
    popup = SuggestionPopup(lambda: (50, 50, 16), lambda: (0, 0))
    popup._show(["skole", "skov"], 1)
    assert popup.isVisible()
    texts = [row.text() for row in popup.rows if row.isVisible()]
    assert len(texts) == 2
    assert "F1" in texts[0] and "skole" in texts[0]
    assert texts[1].startswith("<b>")  # det valgte
    popup._show(["skal"], -1)
    assert [row.isVisible() for row in popup.rows] == [True, False]
    popup.hide()


def test_falls_back_to_mouse_without_caret(app) -> None:
    popup = SuggestionPopup(lambda: None, lambda: (300, 300))
    popup._show(["skole"], -1)
    assert popup.pos().y() > 300
    popup.hide()


def test_click_reports_index(app) -> None:
    popup = SuggestionPopup(lambda: None, lambda: (0, 0))
    popup._show(["skole", "skov"], -1)
    clicks: list[tuple[int, bool]] = []
    popup.clicked.connect(lambda i, right: clicks.append((i, right)))
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    QTest.mouseClick(popup.rows[1], Qt.MouseButton.LeftButton)
    QTest.mouseClick(popup.rows[0], Qt.MouseButton.RightButton)
    assert clicks == [(1, False), (0, True)]
    popup.hide()
