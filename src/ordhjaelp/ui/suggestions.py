"""Forslagsvinduet ved markøren (Windows; på Linux viser IBus selv forslagene).

Vinduet må aldrig tage fokus fra det program, eleven skriver i. Derfor er det et
værktøjstip-vindue, der vises uden at blive aktivt, og som ikke kan aktiveres
ved klik.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

CaretPosition = Callable[[], tuple[int, int, int] | None]  # (x, y, højde) i skærmpixels
MousePosition = Callable[[], tuple[int, int]]
GAP = 4  # afstand mellem markøren og vinduet


def to_logical(x: int, y: int) -> QPoint:
    """Skærmpixels fra Windows → Qt's punkter (forskellige ved skalering, fx 125 %)."""
    for screen in QGuiApplication.screens():
        geo, ratio = screen.geometry(), screen.devicePixelRatio()
        native = QRect(geo.topLeft(), geo.size() * ratio)
        if native.contains(x, y):
            return QPoint(
                geo.left() + round((x - geo.left()) / ratio),
                geo.top() + round((y - geo.top()) / ratio),
            )
    return QPoint(x, y)


def place_below(anchor: QPoint, line_height: int, size: QRect, screen: QRect) -> QPoint:
    """Under markøren – eller over den, hvis der ikke er plads nedenfor."""
    x = min(max(anchor.x(), screen.left()), screen.right() - size.width())
    y = anchor.y() + line_height + GAP
    if y + size.height() > screen.bottom():
        y = anchor.y() - size.height() - GAP
    return QPoint(x, max(y, screen.top()))


class _Row(QLabel):
    def __init__(self, popup: SuggestionPopup, index: int) -> None:
        super().__init__()
        self._popup = popup
        self._index = index
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        right = event.button() == Qt.MouseButton.RightButton
        self._popup.clicked.emit(self._index, right)


class _Signals(QObject):
    show = Signal(list, int)
    hide = Signal()


class SuggestionPopup(QFrame):
    """Viser op til fem forslag. Metoderne kan kaldes fra alle tråde."""

    clicked = Signal(int, bool)  # forslagets nummer, højreklik

    def __init__(
        self,
        caret: CaretPosition,
        mouse: MousePosition,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._caret = caret
        self._mouse = mouse
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFrameShape(QFrame.Shape.Box)
        self.setStyleSheet(
            "SuggestionPopup { background: palette(base); border: 1px solid palette(mid); }"
            "QLabel { padding: 3px 8px; font-size: 13pt; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.rows: list[_Row] = []
        self._signals = _Signals()
        self._signals.show.connect(self._show)
        self._signals.hide.connect(self.hide)

    # -- fra alle tråde ------------------------------------------------------
    def show_candidates(self, candidates: list[str], cursor: int) -> None:
        self._signals.show.emit(candidates, cursor)

    def hide_candidates(self) -> None:
        self._signals.hide.emit()

    # -- i brugerfladens tråd ---------------------------------------------
    def _show(self, candidates: list[str], cursor: int) -> None:
        layout = self.layout()
        while len(self.rows) < len(candidates):
            row = _Row(self, len(self.rows))
            self.rows.append(row)
            layout.addWidget(row)
        for i, row in enumerate(self.rows):
            if i >= len(candidates):
                row.hide()
                continue
            if i == cursor:  # det valgte: markeringsfarve, så det kan ses tydeligt
                row.setText(f"<b>F{i + 1}&nbsp;&nbsp;{candidates[i]}</b>")
                row.setStyleSheet(
                    "background: palette(highlight); color: palette(highlighted-text);"
                )
            else:
                row.setText(f'<span style="color:gray">F{i + 1}</span>&nbsp;&nbsp;{candidates[i]}')
                row.setStyleSheet("")
            row.show()
        self.adjustSize()
        self._move_to_caret()
        if not self.isVisible():
            self.show()
            self._no_activate()
        self.raise_()

    def _move_to_caret(self) -> None:
        caret = self._caret()
        if caret is not None:
            x, y, height = caret
        else:
            (x, y), height = self._mouse(), 20
        anchor = to_logical(x, y)
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        line = max(1, round(height / screen.devicePixelRatio()))
        self.move(place_below(anchor, line, self.rect(), screen.availableGeometry()))

    def _no_activate(self) -> None:
        """Sikr at klik på vinduet ikke tager fokus fra programmet (Windows)."""
        if sys.platform != "win32":
            return
        from ordhjaelp.platform.windows import win32

        user32 = win32.user32()
        hwnd = int(self.winId())
        style = user32.GetWindowLongPtrW(hwnd, win32.GWL_EXSTYLE)
        extra = win32.WS_EX_NOACTIVATE | win32.WS_EX_TOOLWINDOW | win32.WS_EX_TOPMOST
        if style & extra != extra:
            user32.SetWindowLongPtrW(hwnd, win32.GWL_EXSTYLE, style | extra)
