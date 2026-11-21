"""Baggrundstjenesten: holder stemmen indlæst og lytter efter genveje, klik og kommandoer."""

from __future__ import annotations

import logging
import os
import signal
import threading

from ordhjaelp import ipc
from ordhjaelp.audio.player import Player
from ordhjaelp.config import Config, voices_dir
from ordhjaelp.platform import get_hotkey_provider, get_selection_provider
from ordhjaelp.platform.base import HotkeyProvider
from ordhjaelp.services.read_aloud import ReadAloudService
from ordhjaelp.tts.piper_engine import PiperEngine, ensure_voice

log = logging.getLogger(__name__)


def run(cfg: Config, hotkeys: bool = True, tray: bool = True) -> None:
    model = ensure_voice(cfg.voice, voices_dir())
    log.info("Indlæser stemmen %s", cfg.voice)
    service = ReadAloudService(
        tts=PiperEngine(model, speed=cfg.speed),
        player=Player(),
        selection=get_selection_provider(),
        use_clipboard_fallback=cfg.use_clipboard_fallback,
    )

    def handle(req: ipc.Request) -> ipc.Response:
        cmd = req.get("cmd")
        if cmd == "ping":
            return {"ok": True}
        if cmd == "laes":
            return {"ok": True, "laeser": service.toggle()}
        if cmd == "sig":
            return {"ok": service.say(str(req.get("tekst", "")))}
        if cmd == "stop":
            service.stop()
            return {"ok": True}
        if cmd == "afslut":
            # Samme vej som Ctrl+C, så både ikon- og baggrundstilstand lukker pænt
            threading.Timer(0.1, os.kill, (os.getpid(), signal.SIGTERM)).start()
            return {"ok": True}
        return {"ok": False, "fejl": f"ukendt kommando: {cmd}"}

    server = ipc.Server(handle)
    server.start()

    hk_holder: list[HotkeyProvider] = []

    def start_hotkeys() -> None:
        # Kører i egen tråd: første gang venter KDE/GNOME på, at brugeren godkender.
        try:
            hk = get_hotkey_provider()
            hk.start(cfg.hotkeys, lambda action: handle({"cmd": action}))
            hk_holder.append(hk)
            log.info("Globale genveje er aktive")
        except Exception as exc:  # noqa: BLE001 - genveje er valgfrie
            log.warning(
                "Globale genveje kunne ikke aktiveres (%s). "
                "Brug ikonet ved uret, eller 'ordhjaelp laes' som genvej.",
                exc,
            )

    if hotkeys:
        threading.Thread(target=start_hotkeys, daemon=True, name="hotkey-setup").start()

    try:
        if not (tray and _run_tray(service)):
            _wait_for_signal()
    finally:
        log.info("Lukker ned")
        service.stop()
        for hk in hk_holder:
            hk.stop()
        server.close()


def _run_tray(service: ReadAloudService) -> bool:
    """Vis ikonet ved uret. Returnerer False, hvis det ikke kan lade sig gøre."""
    try:
        from ordhjaelp.ui.tray import TrayApp
    except ImportError as exc:
        log.warning("Ikon ved uret er ikke tilgængeligt (%s)", exc)
        return False
    if not TrayApp.available():
        log.warning("Skrivebordet har ikke noget område til ikoner ved uret")
        return False
    log.info("Ordhjælp kører. Markér tekst og klik på ikonet ved uret.")
    TrayApp(service).run()
    return True


def _wait_for_signal() -> None:
    log.info("Ordhjælp kører uden ikon. Markér tekst og brug genvejen.")
    done = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: done.set())
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    done.wait()
