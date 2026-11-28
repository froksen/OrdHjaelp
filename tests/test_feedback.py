"""Send en fejl eller et ønske: linket til GitHub og knapperne i menuen og "Om"."""

import getpass
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from ordhjaelp.config import Config  # noqa: E402
from ordhjaelp.ui import about, feedback  # noqa: E402

TEMPLATES = Path(__file__).parent.parent / ".github" / "ISSUE_TEMPLATE"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


@pytest.mark.parametrize("kind", list(feedback.KINDS))
def test_link_opens_the_right_template_with_technical_info(app, kind) -> None:
    url = feedback.issue_url(kind, Config())
    assert url.startswith("https://github.com/froksen/OrdHjaelp/issues/new?")
    query = _query(url)
    assert query["template"] == feedback.KINDS[kind][1]
    assert about.app_version() in query["teknisk"]
    assert "Brug: alt" in query["teknisk"]


@pytest.mark.parametrize("kind", list(feedback.KINDS))
def test_template_exists_and_has_the_technical_field(kind) -> None:
    text = (TEMPLATES / feedback.KINDS[kind][1]).read_text(encoding="utf-8")
    assert "id: teknisk" in text  # linket udfylder feltet med dette id


def test_technical_info_contains_nothing_personal(app) -> None:
    info = feedback.technical_info(Config())
    assert str(Path.home()) not in info
    assert getpass.getuser() not in info.split(":", 1)[1]  # "Ordhjælp:" er ikke et navn


def test_only_active_features_are_listed(app) -> None:
    cfg = Config(read_on_select=True, dictation_enabled=False)
    info = feedback.technical_info(cfg)
    assert "læs ved markering" in info
    assert "diktering" not in info.split("Slået til:")[1].split("\n")[0]


def test_without_settings_the_link_still_works(app) -> None:
    query = _query(feedback.issue_url(feedback.BUG, None))
    assert about.app_version() in query["teknisk"]


def test_long_info_is_shortened_instead_of_cut(app, monkeypatch) -> None:
    monkeypatch.setattr(feedback, "technical_info", lambda cfg: "\n".join(["x" * 300] * 20))
    url = feedback.issue_url(feedback.BUG, None)
    assert len(url) <= feedback.MAX_URL
    assert _query(url)["teknisk"].startswith("x" * 300)


def test_menu_has_both_choices_and_opens_the_browser(app, monkeypatch) -> None:
    opened: list = []
    monkeypatch.setattr(feedback.QDesktopServices, "openUrl", lambda url: opened.append(url))
    menu = feedback.feedback_menu(None, Config)
    assert menu.title() == feedback.MENU_TITLE
    actions = menu.actions()
    assert [a.text() for a in actions] == [label for label, _ in feedback.KINDS.values()]
    actions[1].trigger()
    assert _query(bytes(opened[0].toEncoded()).decode())["template"] == "oenske.yml"


def test_about_dialog_has_the_button(app) -> None:
    dialog = about.AboutDialog()
    assert dialog.feedback.text().startswith(feedback.MENU_TITLE)
    assert len(dialog.feedback.menu().actions()) == 2
