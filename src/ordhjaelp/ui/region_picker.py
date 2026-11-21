"""Frys skærmen og lad eleven trække en firkant om den tekst, der skal læses."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QIODevice, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

HINT = "Træk en firkant om teksten  ·  Esc for at fortryde"
MIN_SIZE = 12  # pixels – mindre end dette regnes for et fejlklik
OCR_MIN_HEIGHT = 400  # små udsnit forstørres – det giver Tesseract bedre resultater


class _ScreenOverlay(QWidget):
    picked = Signal(QImage)
    cancelled = Signal()

    def __init__(self, background: QImage, screen) -> None:  # noqa: ANN001
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._bg = background
        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def _selection(self) -> QRect | None:
        if self._start is None or self._end is None:
            return None
        return QRect(self._start, self._end).normalized()

    def paintEvent(self, _event) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.drawImage(self.rect(), self._bg)
        shade = QColor(0, 0, 0, 120)
        sel = self._selection()
        if sel is None:
            p.fillRect(self.rect(), shade)
        else:
            # Mørklæg alt undtagen markeringen
            r = self.rect()
            p.fillRect(QRect(r.left(), r.top(), r.width(), sel.top() - r.top()), shade)
            p.fillRect(
                QRect(r.left(), sel.bottom() + 1, r.width(), r.bottom() - sel.bottom()), shade
            )
            p.fillRect(QRect(r.left(), sel.top(), sel.left() - r.left(), sel.height()), shade)
            p.fillRect(
                QRect(sel.right() + 1, sel.top(), r.right() - sel.right(), sel.height()), shade
            )
            p.setPen(QPen(QColor("#7c3aed"), 3))
            p.drawRect(sel)
        # Hjælpetekst øverst
        font = QFont(self.font())
        font.setPointSize(16)
        font.setBold(True)
        p.setFont(font)
        box = QRect(0, 24, self.width(), 48)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 170))
        text_w = p.fontMetrics().horizontalAdvance(HINT) + 48
        p.drawRoundedRect(QRect((self.width() - text_w) // 2, box.top(), text_w, 48), 12, 12)
        p.setPen(QColor("white"))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, HINT)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
            return
        self._start = self._end = event.position().toPoint()
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001, N802
        if self._start is not None:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001, N802
        sel = self._selection()
        if sel is None or sel.width() < MIN_SIZE or sel.height() < MIN_SIZE:
            self._start = self._end = None
            self.update()
            return
        sx = self._bg.width() / self.width()
        sy = self._bg.height() / self.height()
        crop = QRect(
            int(sel.x() * sx), int(sel.y() * sy), int(sel.width() * sx), int(sel.height() * sy)
        )
        self.picked.emit(self._bg.copy(crop))

    def keyPressEvent(self, event) -> None:  # noqa: ANN001, N802
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()


class RegionPicker:
    """Viser et overlay på hver skærm. Kalder on_picked(png) eller on_cancel()."""

    def __init__(self, screenshot_png: bytes, on_picked, on_cancel) -> None:  # noqa: ANN001
        self._on_picked = on_picked
        self._on_cancel = on_cancel
        self._overlays: list[_ScreenOverlay] = []
        shot = QImage.fromData(screenshot_png)
        screens = QGuiApplication.screens()
        virtual = screens[0].virtualGeometry() if screens else QRect(0, 0, shot.width(), 1)
        scale = shot.width() / max(1, virtual.width())
        for screen in screens:
            g = screen.geometry().translated(-virtual.topLeft())
            part = shot.copy(
                QRect(
                    int(g.x() * scale),
                    int(g.y() * scale),
                    int(g.width() * scale),
                    int(g.height() * scale),
                )
            )
            overlay = _ScreenOverlay(part, screen)
            overlay.picked.connect(self._picked)
            overlay.cancelled.connect(self._cancelled)
            self._overlays.append(overlay)

    def show(self) -> None:
        for overlay in self._overlays:
            overlay.showFullScreen()
            overlay.activateWindow()
            overlay.raise_()

    def _close(self) -> None:
        for overlay in self._overlays:
            overlay.close()
            overlay.deleteLater()
        self._overlays.clear()

    def _picked(self, image: QImage) -> None:
        self._close()
        self._on_picked(image_to_png(prepare_for_ocr(image)))

    def _cancelled(self) -> None:
        self._close()
        self._on_cancel()


def prepare_for_ocr(image: QImage) -> QImage:
    image = image.convertToFormat(QImage.Format.Format_Grayscale8)
    if image.height() < OCR_MIN_HEIGHT:
        factor = min(4, max(2, OCR_MIN_HEIGHT // max(1, image.height())))
        image = image.scaled(
            image.width() * factor,
            image.height() * factor,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return image


def image_to_png(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())
