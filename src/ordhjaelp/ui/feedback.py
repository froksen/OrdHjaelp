"""Send en fejl eller et ønske: åbner en udfyldt GitHub-sag i browseren.

Ordhjælp sender ikke selv noget. Brugeren ser sagen i browseren, kan rette den og
vælger selv, om den skal oprettes. Der kræves en GitHub-konto, så i praksis er det
ofte en lærer eller forælder, der skriver.

De tekniske oplysninger må aldrig indeholde noget personligt: ingen stier (de
indeholder brugernavnet), ingen tekst, eleven har læst eller skrevet.
"""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Callable
from urllib.parse import quote, urlencode

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QMenu, QWidget

from ordhjaelp.config import Config

ISSUES_URL = "https://github.com/froksen/OrdHjaelp/issues/new"
MENU_TITLE = "Send en fejl eller et ønske"

# Skabelonerne ligger i .github/ISSUE_TEMPLATE/. Feltet "teknisk" udfyldes fra linket.
BUG = "fejl"
WISH = "oenske"
KINDS: dict[str, tuple[str, str]] = {
    BUG: ("Noget virker ikke …", "fejl.yml"),
    WISH: ("Jeg har en idé …", "oenske.yml"),
}

# Windows klipper links over cirka 2000 tegn, når de gives videre til browseren
MAX_URL = 1800


def _installation() -> str:
    from ordhjaelp.platform import is_store_app

    if is_store_app():
        return "Microsoft Store"
    if getattr(sys, "frozen", False):
        return "installationsprogram"
    if sys.prefix.startswith("/usr"):
        return "systemets Python (RPM)"
    return "udviklingsmappe"


def _system() -> str:
    if sys.platform == "win32":
        return f"Windows {platform.release()} ({platform.version()})"
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "ukendt skrivebord")
    session = os.environ.get("XDG_SESSION_TYPE", "ukendt")
    return f"{platform.system()} {platform.release()}, {desktop} ({session})"


def _screen() -> str | None:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return None
    size = screen.size()
    return f"{size.width()}x{size.height()} punkter, skalering {screen.devicePixelRatio():g}"


def _features(cfg: Config) -> str:
    on = [
        name
        for name, active in (
            ("diktering", cfg.dictation_active),
            ("ordforslag", cfg.prediction_active),
            ("læs ved markering", cfg.read_on_select_active),
            ("læs under musen", cfg.read_at_pointer_active),
            ("læs ord ved mellemrum", cfg.read_word_active),
            ("læs sætning ved punktum", cfg.read_sentence_active),
        )
        if active
    ]
    return ", ".join(on) if on else "ingen ekstra"


def technical_info(cfg: Config | None) -> str:
    """Version, system og indstillinger, som hjælper med at finde en fejl."""
    from PySide6 import __version__ as pyside_version

    from ordhjaelp.ui.about import app_version

    lines = [
        f"Ordhjælp: {app_version()}",
        f"Installation: {_installation()}",
        f"System: {_system()}",
        f"Python: {platform.python_version()}, Qt: {pyside_version}",
    ]
    screen = _screen()
    if screen is not None:
        lines.append(f"Skærm: {screen}")
    if cfg is not None:
        lines += [
            f"Brug: {cfg.usage}, visning: {cfg.view}",
            f"Slået til: {_features(cfg)}",
            f"Stemme: {cfg.voice}, talegenkendelse: {cfg.dictation_model}",
        ]
    return "\n".join(lines)


def issue_url(kind: str, cfg: Config | None) -> str:
    """Link til en ny GitHub-sag med den rigtige skabelon og teknikken udfyldt."""
    template = KINDS[kind][1]
    info = technical_info(cfg)
    while True:
        query = urlencode({"template": template, "teknisk": info}, quote_via=quote)
        url = f"{ISSUES_URL}?{query}"
        if len(url) <= MAX_URL or "\n" not in info:
            return url
        info = info.rsplit("\n", 1)[0]  # hellere færre oplysninger end et klippet link


def open_issue(kind: str, cfg: Config | None) -> None:
    QDesktopServices.openUrl(QUrl(issue_url(kind, cfg)))


def feedback_menu(parent: QWidget | None, get_config: Callable[[], Config | None]) -> QMenu:
    """Undermenuen med de to valg. Indstillingerne læses først, når der vælges."""
    menu = QMenu(MENU_TITLE, parent)
    for kind, (label, _) in KINDS.items():
        action = QAction(label, menu)
        action.triggered.connect(lambda _=False, k=kind: open_issue(k, get_config()))
        menu.addAction(action)
    return menu
