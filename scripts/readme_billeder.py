"""Skærmbilleder og en kort demo (GIF) til README.

Tegner Ordhjælps rigtige vinduer (knaplinjen, velkomstguiden, indstillingerne og
ordforslagene) uden at vise dem på skærmen og gemmer dem i docs/billeder/.

Brug (fra repoets rod):
  uv run --with pillow python scripts/readme_billeder.py

Pillow skal kun bruges til at samle demoen til en GIF. Billederne bruger brugerens
rigtige indstillinger: de skrives i en midlertidig mappe.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "billeder"
SCALE = 2  # skarpe skærmbilleder (devicePixelRatio)

# Demoen
W, H = 860, 480
DOC = QRect(30, 70, 800, 300)  # "dokumentet" i demoen
TEXT = "Vikingerne sejlede over havet i lange skibe. De handlede med pelse, sølv og rav."
DICTATED = "Om vinteren fortalte de historier."
BLUE, GREEN, PURPLE = QColor("#2f6fdf"), QColor("#2e9d55"), QColor("#7b4ae2")


# -- Ordhjælps vinduer --------------------------------------------------------------
class _FakeService:
    def add_listener(self, fn: Callable) -> None:
        pass

    def toggle(self) -> None:
        pass

    read_selection = stop = toggle


class _FakeAutostart:
    def is_enabled(self) -> bool:
        return True

    def set_enabled(self, enabled: bool) -> None:
        pass


class _FakeStore:
    def is_installed(self, model) -> bool:  # noqa: ANN001
        return False

    def download(self, model, progress=None, cancel=None) -> None:  # noqa: ANN001
        pass


def _isolate(tmp: Path) -> None:
    """Ingen af billederne må røre brugerens rigtige indstillinger."""
    from ordhjaelp import config as config_mod
    from ordhjaelp.ui import tray_help

    config_mod.config_dir = lambda: tmp
    tray_help.data_dir = lambda: tmp / "data"


def _hooks():
    from ordhjaelp.config import Config
    from ordhjaelp.ui.settings import SettingsHooks

    return SettingsHooks(
        config=Config(),
        set_speed=lambda v: None,
        say=lambda t: None,
        set_clipboard_fallback=lambda v: None,
        set_icon_visible=lambda n, v: None,
        restart=lambda: None,
        autostart=_FakeAutostart(),
    )


def make_tray():
    from ordhjaelp.config import VIEW_TOOLBAR, Config
    from ordhjaelp.ui.tray import TrayApp

    service = _FakeService()
    tray = TrayApp(service, _FakeService(), _FakeService(), {}, _hooks(), Config().hotkeys)
    tray.set_view(VIEW_TOOLBAR)
    tray.toolbar.hide()
    tray.toolbar._shrink()
    return tray


def grab(widget: QWidget, scale: float = SCALE) -> QImage:
    """Tegn et vindue, uden at det vises på skærmen."""
    widget.ensurePolished()
    if widget.layout() is not None:
        widget.layout().activate()
    size = widget.size()
    image = QImage(int(size.width() * scale), int(size.height() * scale), QImage.Format_ARGB32)
    image.setDevicePixelRatio(scale)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image)
    return image


def screenshots(tray) -> None:
    from ordhjaelp.config import Config
    from ordhjaelp.ui.settings import SettingsDialog
    from ordhjaelp.ui.suggestions import SuggestionPopup
    from ordhjaelp.ui.welcome import FirstRunDialog

    grab(tray.toolbar).save(str(OUT / "knaplinje.png"))

    wizard = FirstRunDialog(_FakeStore(), Config(), _FakeAutostart())
    wizard.resize(wizard.sizeHint().expandedTo(wizard.minimumSizeHint()))
    grab(wizard).save(str(OUT / "velkomst.png"))

    dialog = SettingsDialog(_hooks())
    dialog.resize(dialog.sizeHint())
    grab(dialog).save(str(OUT / "indstillinger.png"))

    popup = SuggestionPopup(lambda: None, lambda: (0, 0))
    popup._show(["skole", "skolen", "skoler", "skov"], 0)
    popup.hide()
    grab(popup).save(str(OUT / "ordforslag.png"))


# -- demoen ---------------------------------------------------------------------------
def _font(size: int, bold: bool = False) -> QFont:
    font = QApplication.font()
    font.setPointSizeF(size)
    font.setBold(bold)
    return font


def _pointer(p: QPainter, at: QPoint) -> None:
    """En musepil med spidsen i at."""
    x, y = at.x(), at.y()
    arrow = QPolygonF(
        [
            QPointF(x + dx, y + dy)
            for dx, dy in [(0, 0), (0, 22), (6, 17), (10, 26), (14, 24), (10, 15), (17, 15)]
        ]
    )
    p.setPen(QPen(Qt.GlobalColor.white, 1.5))
    p.setBrush(Qt.GlobalColor.black)
    p.drawPolygon(arrow)


class Demo:
    """Bygger demoens billeder ét ad gangen. Hvert billede vises i et antal millisekunder."""

    def __init__(self, tray) -> None:
        self.tray = tray
        self.frames: list[tuple[QImage, int]] = []
        from ordhjaelp.ui.suggestions import SuggestionPopup

        self.popup = SuggestionPopup(lambda: None, lambda: (0, 0))

    # Byggeklodser
    def _canvas(self, caption: str, step: str = "") -> tuple[QImage, QPainter]:
        image = QImage(W, H, QImage.Format_RGB32)
        image.fill(QColor("#e9edf3"))
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setPen(QColor("#1d2733"))
        p.setFont(_font(15, bold=True))
        p.drawText(QRect(30, 14, W - 60, 44), Qt.AlignmentFlag.AlignVCenter, caption)
        if step:
            p.setFont(_font(10))
            p.setPen(QColor("#5b6675"))
            p.drawText(
                QRect(30, 14, W - 60, 44),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                step,
            )
        return image, p

    def _document(self, p: QPainter, text: str, selected: str = "", caret: bool = False) -> QPoint:
        """Et tekstdokument. Giver punktet lige efter den sidste tekst (til markøren)."""
        p.setPen(QPen(QColor("#c5ccd6"), 1))
        p.setBrush(Qt.GlobalColor.white)
        p.drawRoundedRect(DOC, 8, 8)
        p.setBrush(QColor("#f4f6f9"))
        p.drawRect(QRect(DOC.x() + 1, DOC.y() + 1, DOC.width() - 2, 28))
        p.setPen(QColor("#5b6675"))
        p.setFont(_font(9))
        p.drawText(
            QRect(DOC.x() + 12, DOC.y(), 400, 30), Qt.AlignmentFlag.AlignVCenter, "Vikinger.docx"
        )

        font = _font(14)
        p.setFont(font)
        metrics = p.fontMetrics()
        left, top, width = DOC.x() + 30, DOC.y() + 55, DOC.width() - 60
        line_h = int(metrics.height() * 1.5)
        x, y = left, top
        sel_start = text.find(selected) if selected else -1
        sel_end = sel_start + len(selected)
        pos = 0
        for word in text.split(" "):
            token = word + " "
            w = metrics.horizontalAdvance(token)
            if x + metrics.horizontalAdvance(word) > left + width:
                x, y = left, y + line_h
            if sel_start <= pos < sel_end:
                last = pos + len(word) >= sel_end
                box_w = metrics.horizontalAdvance(word) if last else w
                p.fillRect(
                    QRect(x, y - metrics.ascent(), box_w, metrics.height()), QColor("#b9d3fb")
                )
            p.setPen(QColor("#1d2733"))
            p.drawText(QPoint(x, y), word)
            x += w
            pos += len(token)
        end = QPoint(x - metrics.horizontalAdvance(" "), y)
        if caret:
            p.setPen(QPen(QColor("#1d2733"), 2))
            p.drawLine(end.x() + 2, y - metrics.ascent(), end.x() + 2, y + metrics.descent())
        return end

    def _toolbar(self, p: QPainter) -> QRect:
        bar = grab(self.tray.toolbar, 1)
        place = QPoint(W - bar.width() - 30, H - bar.height() - 22)
        p.drawImage(place, bar)
        return QRect(place, bar.size())

    def _button(self, bar: QRect, index: int) -> QPoint:
        """Midten af knap nr. index (0 = læs op) i knaplinjen."""
        button = list(self.tray.toolbar.buttons.values())[index]
        return bar.topLeft() + button.geometry().center() + self.tray.toolbar._frame.pos()

    def _bubble(self, p: QPainter, text: str, near: QPoint, color: QColor) -> None:
        p.setFont(_font(11, bold=True))
        w = p.fontMetrics().horizontalAdvance(text) + 28
        box = QRect(near.x() - w // 2, near.y() - 62, w, 34)
        box.moveRight(min(box.right(), W - 12))
        path = QPainterPath()
        path.addRoundedRect(QRectF(box), 10, 10)
        p.fillPath(path, color)
        p.setPen(Qt.GlobalColor.white)
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def add(self, image: QImage, p: QPainter, ms: int) -> None:
        p.end()
        self.frames.append((image, ms))

    # Scenerne
    def title(self) -> None:
        image, p = self._canvas("")
        p.setPen(QColor("#1d2733"))
        p.setFont(_font(30, bold=True))
        p.drawText(QRect(0, 140, W, 60), Qt.AlignmentFlag.AlignCenter, "Ordhjælp")
        p.setFont(_font(15))
        p.setPen(QColor("#3a4654"))
        p.drawText(
            QRect(0, 205, W, 40),
            Qt.AlignmentFlag.AlignCenter,
            "Gratis læse- og skrivehjælp til danske elever",
        )
        bar = grab(self.tray.toolbar, 1)
        p.drawImage(QPoint((W - bar.width()) // 2, 280), bar)
        self.add(image, p, 2200)

    def read_aloud(self) -> None:
        step = "1 / 4  Læs op"
        image, p = self._canvas("Markér tekst, og klik på den blå knap", step)
        self._document(p, TEXT, selected=TEXT)
        bar = self._toolbar(p)
        _pointer(p, self._button(bar, 0))
        self.add(image, p, 2200)

        self.tray._set_speaking(True)
        image, p = self._canvas("Ordhjælp læser teksten op med en dansk stemme", step)
        self._document(p, TEXT, selected=TEXT)
        bar = self._toolbar(p)
        self._bubble(p, "Læser op …", self._button(bar, 0), BLUE)
        self.add(image, p, 2400)
        self.tray._set_speaking(False)

    def dictation(self) -> None:
        from ordhjaelp.services.dictation import DictationState

        step = "2 / 4  Diktering"
        image, p = self._canvas("Klik på den grønne knap, og sig det, du vil skrive", step)
        self._document(p, TEXT, caret=True)
        bar = self._toolbar(p)
        _pointer(p, self._button(bar, 1))
        self.add(image, p, 2000)

        self.tray._set_dictation_state(DictationState.RECORDING)
        image, p = self._canvas("Ordhjælp lytter …", step)
        self._document(p, TEXT, caret=True)
        bar = self._toolbar(p)
        self._bubble(p, "Jeg lytter …", self._button(bar, 1), GREEN)
        self.add(image, p, 1800)

        self.tray._set_dictation_state(DictationState.IDLE)
        words = DICTATED.split(" ")
        for n in range(1, len(words) + 1):
            image, p = self._canvas("… og skriver det, du sagde, hvor markøren står", step)
            self._document(p, TEXT + " " + " ".join(words[:n]), caret=True)
            self._toolbar(p)
            self.add(image, p, 2000 if n == len(words) else 250)

    def suggestions(self) -> None:
        step = "3 / 4  Ordforslag"
        base = "Jeg går i "
        typed = "sgole"
        for n in range(1, len(typed) + 1):
            image, p = self._canvas(
                "Skriv, og få forslag, også når ordet staves, som det lyder", step
            )
            end = self._document(p, base + typed[:n], caret=True)
            self._toolbar(p)
            if n >= 3:
                self.popup._show(
                    ["skole", "skolen", "skoler", "skov"][: 2 + n // 2], 0 if n == 5 else -1
                )
                self.popup.hide()
                p.drawImage(QPoint(end.x() - 20, end.y() + 14), grab(self.popup, 1))
            self.add(image, p, 1800 if n == len(typed) else 300)

        image, p = self._canvas("Tryk Tab, så står der det rigtige ord", step)
        self._document(p, base + "skole", caret=True)
        self._toolbar(p)
        self.add(image, p, 2200)

    def screen_read(self) -> None:
        step = "4 / 4  Læs fra skærmen"
        poster = QRect(60, 90, 420, 250)

        def scene(caption: str, sel: float, ms: int, bubble: bool = False) -> None:
            image, p = self._canvas(caption, step)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#f3e3c3"))
            p.drawRoundedRect(poster, 6, 6)
            p.setBrush(QColor("#b5552f"))
            p.drawRect(QRect(poster.x(), poster.y(), poster.width(), 48))
            p.setPen(Qt.GlobalColor.white)
            p.setFont(_font(16, bold=True))
            p.drawText(
                QRect(poster.x(), poster.y(), poster.width(), 48),
                Qt.AlignmentFlag.AlignCenter,
                "BILLEDE / SCANNET SIDE",
            )
            p.setPen(QColor("#3b2a1a"))
            p.setFont(_font(15, bold=True))
            p.drawText(
                QRect(poster.x() + 20, poster.y() + 80, poster.width() - 40, 120),
                Qt.TextFlag.TextWordWrap,
                "Skibene kunne sejle\nbåde på havet og op\nad floderne.",
            )
            bar = self._toolbar(p)
            if sel > 0:
                area = QRect(
                    poster.x() + 10, poster.y() + 70, int((poster.width() - 20) * sel), 120
                )
                p.setBrush(QColor(123, 74, 226, 40))
                p.setPen(QPen(PURPLE, 2, Qt.PenStyle.DashLine))
                p.drawRect(area)
                _pointer(p, area.bottomRight())
            else:
                _pointer(p, self._button(bar, 2))
            if bubble:
                self._bubble(p, "Læser op …", self._button(bar, 2), PURPLE)
            self.add(image, p, ms)

        scene("Tekst i et billede eller en scannet PDF? Klik på den lilla knap", 0, 2000)
        for f in (0.3, 0.6, 0.9, 1.0):
            scene("Træk en firkant om teksten", f, 300 if f < 1 else 1200)
        scene("Ordhjælp finder teksten og læser den op", 1.0, 2200, bubble=True)

    def end(self) -> None:
        image, p = self._canvas("")
        p.setPen(QColor("#1d2733"))
        p.setFont(_font(24, bold=True))
        p.drawText(QRect(0, 150, W, 50), Qt.AlignmentFlag.AlignCenter, "Ordhjælp")
        p.setFont(_font(14))
        p.setPen(QColor("#3a4654"))
        lines = [
            "Gratis og open source",
            "Kører uden internet: intet sendes ud",
            "Til Windows og Fedora Linux (KDE Plasma)",
        ]
        for i, line in enumerate(lines):
            p.drawText(QRect(0, 215 + i * 34, W, 30), Qt.AlignmentFlag.AlignCenter, line)
        self.add(image, p, 3500)


def save_gif(frames: list[tuple[QImage, int]], path: Path) -> None:
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow mangler. Kør: uv run --with pillow python scripts/readme_billeder.py")
    images = []
    for image, _ms in frames:
        rgb = image.convertToFormat(QImage.Format_RGB888)
        raw = bytes(rgb.constBits())[: rgb.sizeInBytes()]
        pil = Image.frombuffer(
            "RGB", (rgb.width(), rgb.height()), raw, "raw", "RGB", rgb.bytesPerLine(), 1
        )
        images.append(pil.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=[ms for _img, ms in frames],
        loop=0,
        optimize=True,
        disposal=1,
    )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        _isolate(Path(tmp))
        tray = make_tray()
        screenshots(tray)
        demo = Demo(tray)
        demo.title()
        demo.read_aloud()
        demo.dictation()
        demo.suggestions()
        demo.screen_read()
        demo.end()
        save_gif(demo.frames, OUT / "demo.gif")
        tray.tray.hide()
    del app
    for f in sorted(OUT.iterdir()):
        print(f"{f.relative_to(ROOT)}  {f.stat().st_size // 1024} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
