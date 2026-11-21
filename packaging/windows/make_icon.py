"""Lav ordhjaelp.ico ud fra programmets SVG-ikon (til Ordhjaelp.exe og installeren).

Brug: python make_icon.py <svg> <ico>
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SIZE = 256  # Windows skalerer selv ned til de mindre størrelser


def main(svg: str, ico: str) -> int:
    QGuiApplication([])
    renderer = QSvgRenderer(svg)
    if not renderer.isValid():
        print(f"Kan ikke læse {svg}", file=sys.stderr)
        return 1
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    if not image.save(ico, "ICO"):
        print(f"Kan ikke gemme {ico}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
