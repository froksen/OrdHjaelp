"""Knaplinjen: en lille linje med store knapper, der ligger øverst på skærmen.

Den erstatter ikonerne ved uret, når der er mange funktioner. Linjen tager aldrig
fokus fra det program, eleven arbejder i: ellers ville den markerede tekst eller
skrivemarkøren forsvinde, før der bliver læst op eller dikteret.

Ren Qt, så den virker på Linux og Windows. Eleven flytter linjen ved at trække i
håndtaget (⠿), og Ordhjælp husker, hvor den lå, og om den var foldet ind. På Wayland
må programmer hverken se eller bestemme, hvor deres vinduer ligger. Der huskes kun,
om linjen var foldet ind. Linjen starter nederst til højre over opgavelinjen: på
Wayland beder vi KDE (KWin) om at flytte den dertil, holde den øverst og holde den
ude af opgavelinjen (det ignorerer Wayland ellers).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QToolButton, QWidget

from ordhjaelp.ui.shortcuts import shortcut_for

log = logging.getLogger(__name__)

ICON_SIZE = 26  # skærmpunkter; knapperne er 8 større
DIM_OPACITY = 0.55  # gennemsigtig, når musen ikke er over linjen
DIM_DELAY_MS = 2500
SAVE_DELAY_MS = 500  # gem først, når eleven har sluppet linjen
MARGIN = 24  # afstand til skærmkanten første gang
# Wayland: vent lidt, så skrivebordet har vist vinduet, før det flyttes (og prøv igen)
WAYLAND_PLACE_DELAYS = (0.2, 1.0)


def _is_wayland() -> bool:
    return QGuiApplication.platformName().startswith("wayland")


def load_state(path: Path | None) -> dict:
    """Det gemte: {"x": …, "y": …, "foldet": …}. Tomt, hvis filen mangler eller er i stykker."""
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)  # atomisk: aldrig en halvt skrevet fil


def place_on_screen(saved: QPoint | None, size: QSize, areas: list[QRect]) -> QPoint:
    """Den gemte plads, hvis linjen kan ses der. Ellers nederst til højre over uret.

    Linjen skal ligge helt inden for en skærm. Ellers kunne den være væk, fx når en
    bærbar pc har været sluttet til en ekstra skærm, som ikke er der mere.
    """
    if saved is not None:
        for area in areas:
            if area.contains(QRect(saved, size)):
                return saved
    if not areas:
        return QPoint(0, 0)
    area = areas[0]
    return QPoint(area.right() - size.width() - MARGIN, area.bottom() - size.height() - MARGIN)


def tooltip_with_key(text: str, hotkeys: dict[str, str] | None, action: str) -> str:
    """Forklaringen på en knap, med genvejen i parentes (fx "Læs op (Ctrl+Alt+L)")."""
    key = shortcut_for(hotkeys, action)
    return f"{text} ({key})" if key else text


class _Grip(QWidget):
    """Håndtaget, man trækker linjen i (seks prikker)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(16, ICON_SIZE + 8)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("Træk her for at flytte knaplinjen")

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.palette().placeholderText())
        cx, cy = self.width() / 2, self.height() / 2
        for dx in (-3, 3):
            for dy in (-7, 0, 7):
                p.drawEllipse(QPoint(round(cx + dx), round(cy + dy)), 2, 2)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            # Skrivebordet flytter vinduet: virker også på Wayland, hvor move() ignoreres
            if handle is not None and handle.startSystemMove():
                return
            self._offset = event.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        offset = getattr(self, "_offset", None)
        if offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - offset)

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:  # noqa: N802
        self._offset = None


class Toolbar(QWidget):
    """Knaplinjen. Knapperne tilføjes med add_button og kan skjules enkeltvis."""

    def __init__(
        self,
        app_icon: QIcon,
        menu: QMenu | None = None,
        state_path: Path | None = None,
        wayland_placer: Callable[[str, int], bool] | None = None,
    ) -> None:
        """:param state_path: filen, hvor placeringen huskes (None: huskes ikke).
        :param wayland_placer: lægger et vindue (titel, margen) nederst til højre, altid
            øverst og uden for opgavelinjen på Wayland, hvor Qt ikke kan. Kaldes i en
            baggrundstråd.
        """
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Ordhjælp")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._frame = QFrame(self)
        self._frame.setObjectName("knaplinje")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._frame)
        self._row = QHBoxLayout(self._frame)
        self._row.setContentsMargins(4, 4, 4, 4)
        self._row.setSpacing(2)
        self._row.addWidget(_Grip(self._frame))
        self._apply_style()

        self.buttons: dict[str, QToolButton] = {}
        self._wanted: dict[str, bool] = {}
        self._folded = False

        # Sidst på linjen: menuen (indstillinger m.m.) og fold ind/ud
        self._tail: list[QToolButton] = []
        if menu is not None:
            more = self._make_button("⋯", "Mere: indstillinger, genveje og luk")
            more.setMenu(menu)
            more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            more.setStyleSheet("QToolButton::menu-indicator { image: none; }")
            self._more = more
            self._tail.append(more)
        self._fold = self._make_button("‹", "Fold knaplinjen ind")
        self._fold.setFixedWidth(20)
        self._fold.clicked.connect(lambda: self.set_folded(not self._folded))
        self._tail.append(self._fold)
        self._app_icon = app_icon
        # En kort besked til eleven (fx fra diktering) vises i selve linjen. Et eget
        # vindue kan ikke placeres på Wayland, men linjen ligger der, hvor eleven har den.
        self._message = QLabel(self._frame)
        self._message.setObjectName("besked")
        self._message.setVisible(False)
        self._row.addWidget(self._message)
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self.hide_message)
        for button in self._tail:
            self._row.addWidget(button)

        self._dim_timer = QTimer(self)
        self._dim_timer.setSingleShot(True)
        self._dim_timer.setInterval(DIM_DELAY_MS)
        self._dim_timer.timeout.connect(lambda: self._set_opacity(DIM_OPACITY))

        self._state_path = state_path
        self._wayland_placer = wayland_placer
        self._placed = False  # først når linjen er placeret, er en flytning elevens egen
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self._save)

    # -- knapper --------------------------------------------------------------
    def add_button(
        self, name: str, icon: QIcon, tooltip: str, on_click: Callable[[], None]
    ) -> QToolButton:
        button = self._make_button("", tooltip)
        button.setIcon(icon)
        button.clicked.connect(on_click)
        self._row.insertWidget(1 + len(self.buttons), button)  # efter håndtaget
        self.buttons[name] = button
        self._wanted[name] = True
        return button

    def set_button(self, name: str, icon: QIcon, tooltip: str) -> None:
        """Skift ikon og forklaring, fx højttaler → stop under oplæsning."""
        button = self.buttons.get(name)
        if button is not None:
            button.setIcon(icon)
            button.setToolTip(tooltip)

    def set_button_visible(self, name: str, visible: bool) -> None:
        if name in self.buttons:
            self._wanted[name] = visible
            self.buttons[name].setVisible(visible and not self._folded)
            self._shrink()

    def set_folded(self, folded: bool) -> None:
        """Foldet ind: kun en lille fane med Ordhjælp-ikonet er tilbage."""
        self._folded = folded
        for name, button in self.buttons.items():
            button.setVisible(self._wanted[name] and not folded)
        if hasattr(self, "_more"):
            self._more.setVisible(not folded)
        if folded:
            # Ikonet og en pil: så ligner fanen ikke knappen "Læs op"
            self._fold.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self._fold.setFixedWidth(ICON_SIZE + 30)
            self._fold.setText("›")
            self._fold.setIcon(self._app_icon)
            self._fold.setToolTip("Vis Ordhjælps knapper")
        else:
            self._fold.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            self._fold.setFixedWidth(20)
            self._fold.setIcon(QIcon())
            self._fold.setText("‹")
            self._fold.setToolTip("Fold knaplinjen ind")
        self._shrink()
        if self._placed:
            self._save_timer.start()

    def show_message(self, text: str, msecs: int) -> None:
        """Vis en besked i linjen i msecs millisekunder (også når linjen er foldet ind)."""
        self._message.setText(text)
        self._message.setVisible(True)
        self._dim_timer.stop()
        self._set_opacity(1.0)
        self._shrink()
        self._message_timer.start(msecs)

    def hide_message(self) -> None:
        self._message.setVisible(False)
        self._message.clear()
        self._shrink()
        self._dim_timer.start()

    @property
    def message(self) -> str:
        """Beskeden, der vises lige nu ("" = ingen)."""
        return self._message.text() if self._message.isVisibleTo(self) else ""

    @property
    def folded(self) -> bool:
        return self._folded

    def show_at_saved_place(self) -> None:
        """Vis linjen, hvor eleven sidst havde den, og foldet ind, hvis den var det."""
        state = load_state(self._state_path)
        self.set_folded(bool(state.get("foldet", False)))
        saved = None
        if isinstance(state.get("x"), int) and isinstance(state.get("y"), int):
            saved = QPoint(state["x"], state["y"])
        if not _is_wayland():  # på Wayland ignoreres move(), og skrivebordet vælger
            primary = QGuiApplication.primaryScreen()
            screens = [primary, *(s for s in QGuiApplication.screens() if s is not primary)]
            areas = [s.availableGeometry() for s in screens if s is not None]
            self.move(place_on_screen(saved, self.size(), areas))
        self.show()
        if _is_wayland() and self._wayland_placer is not None:
            title = self.windowTitle()  # læses her: Qt-objekter hører til hovedtråden
            threading.Thread(target=self._place_on_wayland, args=(title,), daemon=True).start()
        self._placed = True
        self._dim_timer.start()

    def _place_on_wayland(self, title: str) -> None:
        """Bed KDE om at lægge linjen i hjørnet, altid øverst og uden for opgavelinjen."""
        assert self._wayland_placer is not None
        for delay in WAYLAND_PLACE_DELAYS:
            time.sleep(delay)
            if self._wayland_placer(title, MARGIN):
                return
        log.info("KDE kunne ikke lægge knaplinjen i hjørnet og holde den øverst")

    # -- intern ---------------------------------------------------------------
    def _shrink(self) -> None:
        """Gør vinduet så lille som knapperne (også når nogle lige er skjult)."""
        self._row.activate()
        self.layout().activate()
        # Fast størrelse, ikke resize(): på Wayland kan skrivebordet ellers beholde den
        # gamle bredde. Så passer vinduet og knapperne ikke sammen, og klik rammer forkert
        # (den foldede fane kunne ikke foldes ud igen).
        self.setFixedSize(self.minimumSizeHint())

    def _make_button(self, text: str, tooltip: str) -> QToolButton:
        button = QToolButton(self._frame)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        button.setFixedSize(ICON_SIZE + 8, ICON_SIZE + 8)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAutoRaise(True)
        return button

    def _apply_style(self) -> None:
        pal = self.palette()
        bg = pal.window().color()
        border = QColor(pal.mid().color())
        self._frame.setStyleSheet(
            f"""
            QFrame#knaplinje {{
                background: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 240);
                border: 1px solid {border.name()};
                border-radius: 12px;
            }}
            QLabel#besked {{ font-size: 15px; padding: 0 8px; }}
            QToolButton {{ border: none; border-radius: 8px; font-size: 16px; }}
            QToolButton:hover {{ background: rgba(127, 127, 127, 50); }}
            QToolButton:pressed {{ background: rgba(127, 127, 127, 90); }}
            """
        )

    def moveEvent(self, event) -> None:  # noqa: ANN001, N802
        super().moveEvent(event)
        if self._placed and not _is_wayland():
            self._save_timer.start()  # nulstilles ved hver bevægelse

    def _save(self) -> None:
        if self._state_path is None:
            return
        state: dict = {"foldet": self._folded}
        if not _is_wayland():  # på Wayland er pos() altid (0, 0) og siger ikke noget
            state |= {"x": self.x(), "y": self.y()}
        try:
            save_state(self._state_path, state)
        except OSError as exc:
            log.warning("Kunne ikke huske knaplinjens placering: %s", exc)

    def _set_opacity(self, value: float) -> None:
        # Wayland kan ikke gøre et helt vindue gennemsigtigt (Qt advarer ved hvert forsøg)
        if not _is_wayland():
            self.setWindowOpacity(value)

    def enterEvent(self, event) -> None:  # noqa: ANN001, N802
        self._dim_timer.stop()
        self._set_opacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001, N802
        self._dim_timer.start()
        super().leaveEvent(event)
