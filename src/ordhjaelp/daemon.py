"""Baggrundstjenesten: holder stemmen indlæst og lytter efter genveje og kommandoer."""

from __future__ import annotations

import logging
import signal
import threading

from ordhjaelp import ipc
from ordhjaelp.audio.player import Player
from ordhjaelp.config import Config, voices_dir
from ordhjaelp.platform import PlatformNotSupported, get_hotkey_provider, get_selection_provider
from ordhjaelp.services.read_aloud import ReadAloudService
from ordhjaelp.tts.piper_engine import PiperEngine, ensure_voice

log = logging.getLogger(__name__)


def run(cfg: Config, hotkeys: bool = True) -> None:
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
        return {"ok": False, "fejl": f"ukendt kommando: {cmd}"}

    def on_hotkey(action: str) -> None:
        log.debug("Genvej: %s", action)
        handle({"cmd": action})

    server = ipc.Server(handle)
    server.start()

    hk = None
    if hotkeys:
        try:
            hk = get_hotkey_provider()
            hk.start(cfg.hotkeys, on_hotkey)
            log.info("Globale genveje er aktive")
        except (PlatformNotSupported, Exception) as exc:  # noqa: BLE001
            hk = None
            log.warning(
                "Globale genveje kunne ikke aktiveres (%s). "
                "Brug 'ordhjaelp laes' som genvej i systemindstillingerne.",
                exc,
            )

    log.info("Ordhjælp kører. Markér tekst og tryk %s.", cfg.hotkeys.get("laes"))
    done = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: done.set())
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    done.wait()

    log.info("Lukker ned")
    service.stop()
    if hk:
        hk.stop()
    server.close()
