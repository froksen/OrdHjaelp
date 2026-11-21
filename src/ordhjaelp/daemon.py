"""Baggrundstjenesten: holder stemmen indlæst og lytter efter genveje, klik og kommandoer."""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from collections.abc import Callable

from ordhjaelp import ipc
from ordhjaelp.audio.player import Player
from ordhjaelp.config import Config, learned_words_path, lexicon_path, voices_dir, whisper_dir
from ordhjaelp.platform import (
    PlatformNotSupported,
    get_autostart,
    get_hotkey_provider,
    get_input_method,
    get_pointer_text,
    get_screen_capture,
    get_selection_provider,
    get_text_injector,
)
from ordhjaelp.platform.base import HotkeyProvider
from ordhjaelp.services.dictation import DictationService
from ordhjaelp.services.pointer_read import UNITS, PointerReadService
from ordhjaelp.services.read_aloud import ReadAloudService
from ordhjaelp.services.screen_read import ScreenReadService
from ordhjaelp.services.selection_read import SelectionAutoReader
from ordhjaelp.services.word_prediction import WordPredictionService
from ordhjaelp.tts.piper_engine import PiperEngine, ensure_voice

log = logging.getLogger(__name__)

# Kommandoer og genveje til læs under musen -> hvad der skal læses
POINTER_COMMANDS = {f"laes_{unit}": unit for unit in UNITS}


def run(cfg: Config, hotkeys: bool = True, tray: bool = True) -> None:
    model = ensure_voice(cfg.voice, voices_dir())
    log.info("Indlæser stemmen %s", cfg.voice)
    tts = PiperEngine(model, speed=cfg.speed)
    selection = get_selection_provider()
    service = ReadAloudService(
        tts=tts,
        player=Player(),
        selection=selection,
        use_clipboard_fallback=cfg.use_clipboard_fallback,
    )
    set_read_on_select = _make_read_on_select(selection, service)
    if cfg.read_on_select:
        set_read_on_select(True)
    dictation = _make_dictation(cfg, service) if cfg.dictation_enabled else None
    screen = _make_screen_reader(service)
    pointer = _make_pointer_reader(service) if cfg.read_at_pointer else None
    prediction = WordPredictionService(lexicon_path(), learned_words_path())
    prediction.load_in_background()
    # Handlinger som kun brugerfladen kan udføre (fx vise markeringsoverlay)
    ui_actions: dict[str, Callable[[], None]] = {}
    restart_requested = threading.Event()

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
        if cmd == "forslag":
            return {"ok": True, "forslag": prediction.suggest(str(req.get("ord", "")))}
        if cmd == "skrevet":  # fra ordforslag: et ord og/eller en sætning er skrevet færdig
            return {"ok": True, "laeser": _read_while_typing(cfg, service, req)}
        if cmd in POINTER_COMMANDS:
            if pointer is None:
                return {"ok": False, "fejl": "Læs under musen er slået fra i indstillingerne"}
            # Egen tråd: genveje kommer fra portal-tråden, som ikke må vente på AT-SPI
            threading.Thread(
                target=pointer.read, args=(POINTER_COMMANDS[cmd],), daemon=True,
                name="pointer-read",
            ).start()  # fmt: skip
            return {"ok": True}
        if cmd == "laer":
            prediction.learn(str(req.get("ord", "")))
            return {"ok": True}
        if cmd == "skaerm":
            action = ui_actions.get("skaerm")
            if action is None:
                return {"ok": False, "fejl": "Læs fra skærmen kræver ikonet ved uret"}
            action()
            return {"ok": True}
        if cmd == "skriv":  # til fejlfinding: skriv tekst ind i det aktive program
            if dictation is None:
                return {"ok": False, "fejl": "Diktering er slået fra i indstillingerne"}
            dictation.insert_text(str(req.get("tekst", "")))
            return {"ok": True}
        if cmd == "dikter":
            if dictation is None:
                return {"ok": False, "fejl": "Diktering er slået fra i indstillingerne"}
            return {"ok": True, "tilstand": dictation.toggle().value}
        if cmd == "afslut":
            # Samme vej som Ctrl+C, så både ikon- og baggrundstilstand lukker pænt
            threading.Timer(0.1, _request_shutdown).start()
            return {"ok": True}
        return {"ok": False, "fejl": f"ukendt kommando: {cmd}"}

    server = ipc.Server(handle)
    server.start()

    hk_holder: list[HotkeyProvider] = []

    def start_hotkeys() -> None:
        # Kører i egen tråd: første gang venter KDE/GNOME på, at brugeren godkender.
        try:
            hk = get_hotkey_provider()
            bindings = dict(cfg.hotkeys)
            if dictation is None:
                bindings.pop("dikter", None)
            if screen is None:
                bindings.pop("skaerm", None)
            if pointer is None:
                for name in POINTER_COMMANDS:
                    bindings.pop(name, None)
            hk.start(bindings, lambda action: handle({"cmd": action}))
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

    input_method = None
    if cfg.prediction_enabled:
        try:
            input_method = get_input_method()
            input_method.start()  # starter også senere af sig selv, hvis IBus mangler nu
        except Exception as exc:  # noqa: BLE001 - ordforslag er valgfrit
            log.warning("Ordforslag er ikke tilgængeligt: %s", exc)
            input_method = None

    def restart() -> None:
        restart_requested.set()
        _request_shutdown()  # luk pænt – derefter startes forfra

    try:
        hooks = _settings_hooks(cfg, tts, service, restart, set_read_on_select) if tray else None
        if not (tray and _run_tray(service, dictation, screen, ui_actions, hooks)):
            _wait_for_signal()
    finally:
        log.info("Lukker ned")
        prediction.save()
        if input_method:
            input_method.stop()
        service.stop()
        for hk in hk_holder:
            hk.stop()
        server.close()

    if restart_requested.is_set():
        log.info("Starter forfra med nye indstillinger")
        # Altid via "-m ordhjaelp": virker både fra udviklingsmappen og fra RPM-installationen
        os.execv(sys.executable, [sys.executable, "-m", "ordhjaelp", *sys.argv[1:]])


def _make_read_on_select(selection, service: ReadAloudService) -> Callable[[bool], None]:  # noqa: ANN001
    """Læs ved markering. Platformen begynder først at lytte, når det slås til."""
    reader = SelectionAutoReader(service.read_new_selection)
    listening = False

    def set_enabled(enabled: bool) -> None:
        nonlocal listening
        if enabled and not listening:
            listening = selection.on_change(reader.selection_changed)
        reader.enabled = enabled and listening

    return set_enabled


def _settings_hooks(
    cfg: Config, tts: PiperEngine, service: ReadAloudService, restart, set_read_on_select
):  # noqa: ANN001, ANN202
    try:
        from ordhjaelp.ui.settings import SettingsHooks
    except ImportError:
        return None
    try:
        autostart = get_autostart()
    except PlatformNotSupported:
        autostart = None

    def set_speed(speed: float) -> None:
        tts.speed = speed

    def set_clipboard(enabled: bool) -> None:
        service.use_clipboard_fallback = enabled

    return SettingsHooks(
        config=cfg,
        set_speed=set_speed,
        say=service.say,
        set_clipboard_fallback=set_clipboard,
        set_icon_visible=lambda name, visible: None,  # sættes af brugerfladen
        restart=restart,
        autostart=autostart,
        set_read_on_select=set_read_on_select,
    )


def _read_while_typing(cfg: Config, service: ReadAloudService, req: ipc.Request) -> bool:
    """Læs det netop skrevne op – hvis det er slået til i indstillingerne."""
    sentence = str(req.get("saetning") or "")
    word = str(req.get("ord") or "")
    if sentence and cfg.read_sentence_on_period:
        return service.say(sentence)
    if word and cfg.read_word_on_space:
        return service.say(word)
    return False


def _make_dictation(cfg: Config, service: ReadAloudService) -> DictationService | None:
    try:
        from ordhjaelp.audio.cues import Cues
        from ordhjaelp.audio.recorder import Recorder
        from ordhjaelp.stt.whisper_engine import WhisperEngine

        engine = WhisperEngine(cfg.dictation_model, whisper_dir())
        dictation = DictationService(
            recorder=Recorder(),
            transcriber=engine,
            injector=get_text_injector(),
            cues=Cues(),
            before_recording=service.stop,
            tell_user=service.say,
        )
    except Exception as exc:  # noqa: BLE001 - oplæsning skal virke, selv hvis diktering ikke gør
        log.warning("Diktering er ikke tilgængelig: %s", exc)
        return None
    # Hent/indlæs modellen i baggrunden, så første diktering går hurtigt
    threading.Thread(target=_preload, args=(engine,), daemon=True, name="whisper-load").start()
    return dictation


def _preload(engine) -> None:  # noqa: ANN001
    try:
        engine.preload()
    except Exception:
        log.exception("Kunne ikke indlæse talegenkendelse")


def _make_pointer_reader(service: ReadAloudService) -> PointerReadService | None:
    try:
        provider = get_pointer_text()
    except PlatformNotSupported as exc:
        log.warning("Læs under musen er ikke tilgængelig: %s", exc)
        return None
    threading.Thread(target=provider.prepare, daemon=True, name="pointer-prepare").start()
    return PointerReadService(provider, say=service.say)


def _make_screen_reader(service: ReadAloudService) -> ScreenReadService | None:
    from ordhjaelp.ocr.tesseract import TesseractOCR

    if not TesseractOCR.available():
        log.warning(
            "Læs fra skærmen kræver Tesseract: sudo dnf install tesseract tesseract-langpack-dan"
        )
    try:
        capture = get_screen_capture()
    except Exception as exc:  # noqa: BLE001
        log.warning("Læs fra skærmen er ikke tilgængelig: %s", exc)
        return None
    return ScreenReadService(capture, TesseractOCR(), say=service.say, stop_reading=service.stop)


def _run_tray(
    service: ReadAloudService,
    dictation: DictationService | None,
    screen: ScreenReadService | None,
    ui_actions: dict[str, Callable[[], None]],
    hooks=None,  # noqa: ANN001
) -> bool:
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
    TrayApp(service, dictation, screen, ui_actions, hooks).run()
    return True


def _request_shutdown() -> None:
    """Luk pænt via SIGTERM-håndteringen (samme vej som Ctrl+C)."""
    if sys.platform == "win32":
        # os.kill på Windows lukker processen brat uden oprydning. raise_signal kalder
        # vores egen håndtering, ligesom SIGTERM gør på Linux.
        signal.raise_signal(signal.SIGTERM)
    else:
        os.kill(os.getpid(), signal.SIGTERM)


def _wait_for_signal() -> None:
    log.info("Ordhjælp kører uden ikon. Markér tekst og brug genvejen.")
    done = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: done.set())
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    while not done.wait(0.5):  # med tidsgrænse: på Windows afbryder signaler ikke wait()
        pass
