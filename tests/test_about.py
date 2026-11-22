"""Om Ordhjælp: forfattere og de frie projekter, Ordhjælp bygger på."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp.ui import about  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_every_project_has_name_purpose_license_and_link() -> None:
    names = [p.name for _, projects in about.PROJECTS for p in projects]
    assert len(names) == len(set(names))
    for _, projects in about.PROJECTS:
        for p in projects:
            assert p.name and p.what and p.license
            assert p.url.startswith("https://")


def test_the_big_projects_are_credited() -> None:
    names = " ".join(p.name for _, projects in about.PROJECTS for p in projects)
    for name in ("Piper", "Whisper", "Tesseract", "Hunspell", "Stavekontrolden", "Qt", "Python"):
        assert name in names


def test_dialog_shows_authors_projects_and_license(app) -> None:
    dialog = about.AboutDialog()
    text = dialog.browser.toPlainText()
    assert "Ole Frandsen" in text and "qvisty" in text
    for _, projects in about.PROJECTS:
        for p in projects:
            assert p.name in text
    assert "GPL-3.0-or-later" in text
    assert dialog.browser.openExternalLinks()


def test_version_is_shown(app) -> None:
    assert about.app_version() != "ukendt"  # uv sync installerer ordhjaelp
    dialog = about.AboutDialog()
    labels = " ".join(label.text() for label in dialog.findChildren(about.QLabel))
    assert about.app_version() in labels
