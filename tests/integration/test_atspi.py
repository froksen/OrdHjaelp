"""Integrationstest af læs under musen mod en rigtig AT-SPI-bus.

Starter en privat skærm (Xvfb), en privat D-Bus med AT-SPI og et GTK-vindue med
kendt tekst. Musen flyttes med xdotool. Wayland-vejen afprøves med en falsk
KWin, der svarer som den rigtige på KWin-scriptet.

Kræver Xvfb, xdotool, dbus-launch, at-spi2-core og systemets python3-gobject med GTK 3.
Køres med:
    ORDHJAELP_ATSPI_TEST=1 pytest tests/integration/test_atspi.py
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

APP = Path(__file__).with_name("gtk_text_window.py")
BUS_LAUNCHER = "/usr/libexec/at-spi-bus-launcher"
TOOLS = ("Xvfb", "xdotool", "dbus-launch")

pytestmark = pytest.mark.skipif(
    not os.environ.get("ORDHJAELP_ATSPI_TEST")
    or not all(shutil.which(t) for t in TOOLS)
    or not Path(BUS_LAUNCHER).exists(),
    reason="sæt ORDHJAELP_ATSPI_TEST=1 (kræver Xvfb, xdotool, dbus-launch og at-spi2-core)",
)

# Musens placering over ordet "var" i første afsnit og "Næste" i andet
OVER_VAR = (150, 20)
OVER_NAESTE = (40, 60)


def _system_python() -> str:
    for name in ("python3", "python3.13", "python3.12", "python3.11"):
        for exe in (f"/usr/bin/{name}", shutil.which(name)):
            if exe and Path(exe).exists() and exe != sys.executable:
                ok = subprocess.run([exe, "-c", "import gi"], capture_output=True).returncode
                if ok == 0:
                    return exe
    pytest.skip("systemets python3-gobject mangler")


@pytest.fixture(scope="module")
def desktop():
    display = ":97"
    procs = [
        subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1024x768x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    ]
    out = subprocess.run(["dbus-launch", "--sh-syntax"], capture_output=True, text=True).stdout
    env_dbus = dict(re.findall(r"(\w+)='([^']*)'", out))
    old = {
        k: os.environ.get(k)
        for k in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_SESSION_TYPE", "WAYLAND_DISPLAY")
    }
    os.environ.update(
        DISPLAY=display,
        XDG_SESSION_TYPE="x11",
        DBUS_SESSION_BUS_ADDRESS=env_dbus["DBUS_SESSION_BUS_ADDRESS"],
    )
    os.environ.pop("WAYLAND_DISPLAY", None)
    try:
        time.sleep(1)
        procs.append(
            subprocess.Popen(
                [BUS_LAUNCHER, "--launch-immediately"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        time.sleep(1)
        from ordhjaelp.platform.linux.pointer import LinuxPointerText

        LinuxPointerText().prepare()  # slå tilgængelighed til, før vinduet åbnes
        app = subprocess.Popen(
            [_system_python(), str(APP)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        procs.append(app)
        time.sleep(2)
        yield app.pid
    finally:
        for proc in reversed(procs):
            proc.terminate()
        if env_dbus.get("DBUS_SESSION_BUS_PID"):
            subprocess.run(["kill", env_dbus["DBUS_SESSION_BUS_PID"]], check=False)
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _move(x: int, y: int) -> None:
    subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=True)


def test_x11_word_sentence_and_from_here(desktop) -> None:
    from ordhjaelp.platform.linux.pointer import LinuxPointerText

    pointer = LinuxPointerText()
    _move(*OVER_VAR)
    assert pointer.text_at_pointer("ord") == "var"
    assert pointer.text_at_pointer("saetning") == "Den var træt!"
    assert pointer.text_at_pointer("herfra") == (
        "var træt! Så sov den. Næste afsnit kommer her. Og det sidste afsnit."
    )
    _move(*OVER_NAESTE)
    assert pointer.text_at_pointer("ord") == "Næste"


def test_x11_nothing_under_pointer(desktop) -> None:
    from ordhjaelp.platform.linux.pointer import LinuxPointerText

    _move(900, 700)
    assert LinuxPointerText().text_at_pointer("ord") is None


class _FakeKWin:
    """Svarer på loadScript/run som KWin: kalder scriptets callDBus med en position."""

    def __init__(self, report: dict) -> None:
        self.report = report
        self.unloaded: list[str] = []
        self.ready = threading.Event()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        asyncio.run_coroutine_threadsafe(self._start(), self._loop).result(5)

    async def _start(self) -> None:
        import fake_kwin  # ligger ved siden af denne fil
        from dbus_fast import BusType, Message
        from dbus_fast.aio import MessageBus

        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._bus.export("/Scripting", fake_kwin.Scripting(self))
        await self._bus.request_name("org.kde.KWin")
        self._Message = Message

    def script_run(self, script: str) -> None:
        service, path, iface = re.search(
            r'callDBus\("([^"]+)", "([^"]+)", "([^"]+)"', script
        ).groups()
        msg = self._Message(
            destination=service,
            path=path,
            interface=iface,
            member="Report",
            signature="s",
            body=[json.dumps(self.report)],
        )
        self._loop.create_task(self._bus.call(msg))

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._bus.disconnect)


def test_wayland_path_with_fake_kwin(desktop, monkeypatch) -> None:
    from ordhjaelp.platform.linux.pointer import LinuxPointerText

    x, y = OVER_VAR
    kwin = _FakeKWin(
        {
            "x": x + 0.4,
            "y": y,
            "pid": desktop,
            "caption": "Ordhjælp testvindue",
            "clientX": 0,
            "clientY": 0,
        }
    )
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("WAYLAND_DISPLAY", "falsk")
    try:
        _move(900, 700)  # musen på X11 må ikke bruges: positionen skal komme fra KWin
        assert LinuxPointerText().text_at_pointer("saetning") == "Den var træt!"
        assert kwin.unloaded and kwin.unloaded[0].startswith("ordhjaelp-mus-")
    finally:
        kwin.close()
