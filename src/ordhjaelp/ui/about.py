"""Om Ordhjælp: hvem der har lavet det, og hvilke frie projekter det bygger på.

Ordhjælp er lille. Det meste af arbejdet ligger i de open source-projekter, der står i
PROJECTS. Æren skal gå til dem, så listen skal holdes opdateret, når der kommer nye til.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)

HOMEPAGE = "https://github.com/froksen/OrdHjaelp"
LICENSE_NAME = "GPL-3.0-or-later"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

# (navn, rolle, GitHub-bruger)
AUTHORS: list[tuple[str, str, str]] = [
    ("Ole Frandsen", "hovedforfatter og vedligeholder", "froksen"),
    ("qvisty", "bidragsyder: Windows-udgaven, læs ved markering og læs under musen", "qvisty"),
]


@dataclass(frozen=True)
class Project:
    name: str
    what: str  # hvad Ordhjælp bruger det til (kort, i almindeligt dansk)
    license: str
    url: str


# Grupperet efter hvad de gør. Licenserne er dem, projekterne selv oplyser.
PROJECTS: list[tuple[str, list[Project]]] = [
    (
        "Oplæsning",
        [
            Project(
                "Piper",
                "læser teksten op med en dansk stemme",
                "GPL-3.0",
                "https://github.com/OHF-Voice/piper1-gpl",
            ),
            Project(
                "Stemmen da_DK-talesyntese",
                "den danske stemme til Piper",
                "CC0, træningsdata",
                "https://huggingface.co/rhasspy/piper-voices",
            ),
            Project(
                "eSpeak NG",
                "udtale af ordene til Piper",
                "GPL-3.0",
                "https://github.com/espeak-ng/espeak-ng",
            ),
            Project(
                "ONNX Runtime",
                "kører stemmen på computeren",
                "MIT",
                "https://onnxruntime.ai",
            ),
        ],
    ),
    (
        "Diktering",
        [
            Project(
                "Whisper",
                "talegenkendelse fra OpenAI",
                "MIT",
                "https://github.com/openai/whisper",
            ),
            Project(
                "Danske Whisper-modeller",
                "lucasw89, q-henric og CoRal (røst) har gjort Whisper bedre til dansk",
                "MIT / OpenRAIL",
                "https://huggingface.co/lucasw89/whisper-small-danish-ct2-int8",
            ),
            Project(
                "faster-whisper",
                "kører Whisper hurtigt på computeren",
                "MIT",
                "https://github.com/SYSTRAN/faster-whisper",
            ),
            Project(
                "CTranslate2",
                "regnemotoren bag faster-whisper",
                "MIT",
                "https://github.com/OpenNMT/CTranslate2",
            ),
            Project(
                "PyAV og FFmpeg",
                "læser lyd",
                "BSD-3-Clause / LGPL-2.1",
                "https://github.com/PyAV-Org/PyAV",
            ),
            Project(
                "Hugging Face Hub",
                "henter sprogmodellerne",
                "Apache-2.0",
                "https://github.com/huggingface/huggingface_hub",
            ),
        ],
    ),
    (
        "Ordforslag",
        [
            Project(
                "Den danske ordbog fra Stavekontrolden.dk",
                "de rigtige danske ord",
                "GPL-2.0+ / LGPL-2.1+ / MPL-1.1",
                "https://stavekontrolden.dk",
            ),
            Project(
                "Hunspell",
                "slår ord op i ordbogen, fx navne som København",
                "GPL-2.0+ / LGPL-2.1+ / MPL-1.1",
                "https://hunspell.github.io",
            ),
            Project(
                "wordfreq",
                "hvor ofte ordene bruges",
                "Apache-2.0, data CC-BY-SA-4.0",
                "https://github.com/rspeer/wordfreq",
            ),
            Project(
                "RapidFuzz",
                "finder ord, der ligner det skrevne",
                "MIT",
                "https://github.com/rapidfuzz/RapidFuzz",
            ),
        ],
    ),
    (
        "Læs fra skærmen og søgbare PDF'er",
        [
            Project(
                "Tesseract",
                "genkender tekst i billeder",
                "Apache-2.0",
                "https://github.com/tesseract-ocr/tesseract",
            ),
            Project(
                "PDFium og pypdfium2",
                "læser og samler PDF'er",
                "Apache-2.0 / BSD-3-Clause",
                "https://github.com/pypdfium2-team/pypdfium2",
            ),
        ],
    ),
    (
        "Fundamentet",
        [
            Project(
                "Python",
                "programmeringssproget, Ordhjælp er skrevet i",
                "PSF-2.0",
                "https://www.python.org",
            ),
            Project(
                "Qt og Qt for Python (PySide6)",
                "vinduer, knapper og menuer",
                "LGPL-3.0",
                "https://www.qt.io/qt-for-python",
            ),
            Project("NumPy", "regner med lyd", "BSD-3-Clause", "https://numpy.org"),
            Project(
                "sounddevice og PortAudio",
                "afspiller og optager lyd",
                "MIT",
                "https://github.com/spatialaudio/python-sounddevice",
            ),
            Project(
                "platformdirs",
                "finder mapperne til indstillinger og modeller",
                "MIT",
                "https://github.com/tox-dev/platformdirs",
            ),
        ],
    ),
    (
        "Linux",
        [
            Project(
                "dbus-fast",
                "taler med skrivebordet (genveje, skærmbilleder, IBus)",
                "MIT",
                "https://github.com/Bluetooth-Devices/dbus-fast",
            ),
            Project(
                "IBus, AT-SPI og xdg-desktop-portal",
                "ordforslag, markeret tekst og genveje på Linux",
                "LGPL-2.1+",
                "https://github.com/ibus/ibus",
            ),
        ],
    ),
    (
        "Windows-pakken",
        [
            Project(
                "PyInstaller",
                "pakker Ordhjælp, så Python ikke skal installeres",
                "GPL-2.0 med undtagelse",
                "https://pyinstaller.org",
            ),
            Project(
                "Inno Setup",
                "installationsprogrammet",
                "Inno Setup-licensen",
                "https://jrsoftware.org/isinfo.php",
            ),
            Project(
                "MSYS2",
                "Hunspell og Tesseract til Windows",
                "BSD-3-Clause",
                "https://www.msys2.org",
            ),
        ],
    ),
]


def app_version() -> str:
    try:
        return version("ordhjaelp")
    except PackageNotFoundError:
        return "ukendt"


def credits_html() -> str:
    """Hele teksten i dialogen som HTML (links åbnes i browseren)."""
    e = html.escape
    parts = ["<h3>Lavet af</h3><ul>"]
    for name, role, user in AUTHORS:
        parts.append(
            f'<li><b>{e(name)}</b> (<a href="https://github.com/{e(user)}">@{e(user)}</a>):'
            f" {e(role)}</li>"
        )
    parts.append("</ul>")
    parts.append(
        "<h3>Tak til</h3>"
        "<p>Ordhjælp bygger på disse frie og open source-projekter. Uden dem kunne Ordhjælp"
        " ikke læse op, forstå tale eller foreslå ord. Æren er deres.</p>"
    )
    for group, projects in PROJECTS:
        parts.append(f"<h4>{e(group)}</h4><ul>")
        for p in projects:
            parts.append(
                f'<li><a href="{e(p.url)}"><b>{e(p.name)}</b></a>: {e(p.what)}'
                f' <span style="color:gray">({e(p.license)})</span></li>'
            )
        parts.append("</ul>")
    parts.append(
        "<h3>Licens</h3>"
        f'<p>Ordhjælp er fri software under <a href="{LICENSE_URL}">{LICENSE_NAME}</a>.'
        " Du må gerne bruge, dele og ændre det.</p>"
    )
    return "".join(parts)


class AboutDialog(QDialog):
    def __init__(self, icon: QIcon | None = None, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setWindowTitle("Om Ordhjælp")

        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        if icon is not None:
            picture = QLabel()
            picture.setPixmap(icon.pixmap(64, 64))
            head.addWidget(picture, 0, Qt.AlignmentFlag.AlignTop)
        title = QLabel(
            f"<h2>Ordhjælp {html.escape(app_version())}</h2>"
            "Dansk læse- og skrivehjælp<br>"
            f'<a href="{HOMEPAGE}">{HOMEPAGE.removeprefix("https://")}</a>'
        )
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setOpenExternalLinks(True)
        head.addWidget(title, 1)
        layout.addLayout(head)

        # QTextBrowser bryder selv linjerne og kan rulles, også på små skærme
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(credits_html())
        layout.addWidget(self.browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Luk")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(560, 520)
