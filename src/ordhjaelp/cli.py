"""Kommandolinje: ordhjaelp start | laes | stop | sig TEKST | hent-stemme"""

from __future__ import annotations

import argparse
import logging
import sys

from ordhjaelp import ipc
from ordhjaelp.config import config_path, load_config, voices_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ordhjaelp", description="Dansk læse- og skrivehjælp")
    parser.add_argument("-v", "--verbose", action="store_true", help="vis flere detaljer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="start baggrundstjenesten")
    p_start.add_argument(
        "--uden-genveje", action="store_true", help="registrér ikke globale genveje"
    )
    p_start.add_argument("--uden-ikon", action="store_true", help="vis ikke ikonet ved uret")
    sub.add_parser("laes", help="læs markeret tekst op (eller stop, hvis der læses)")
    sub.add_parser("stop", help="stop oplæsning")
    sub.add_parser("afslut", help="luk Ordhjælp helt")
    sub.add_parser("dikter", help="start/stop diktering")
    sub.add_parser("skaerm", help="læs tekst fra et udsnit af skærmen")
    sub.add_parser("laes-ord", help="læs ordet under musen")
    sub.add_parser("laes-saetning", help="læs sætningen under musen")
    sub.add_parser("laes-herfra", help="læs fra musen og videre")
    p_cmp = sub.add_parser("sammenlign-modeller", help="test talegenkendelse med din egen stemme")
    p_cmp.add_argument("--fil", help="brug en gemt optagelse i stedet for mikrofonen")
    p_cmp.add_argument("modeller", nargs="*", help="modeller (standard: alle)")
    p_sig = sub.add_parser("sig", help="læs en tekst op")
    p_sig.add_argument("tekst", nargs="+")
    sub.add_parser("hent-stemme", help="hent den valgte stemme")
    sub.add_parser("status", help="vis om tjenesten kører")
    p_inst = sub.add_parser("installer", help="tilføj Ordhjælp til programmenuen")
    p_inst.add_argument("--autostart", action="store_true", help="start automatisk ved login")
    sub.add_parser("afinstaller", help="fjern Ordhjælp fra programmenu og autostart")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        **_log_target(),
    )
    for noisy in ("httpx", "httpx2", "huggingface_hub", "faster_whisper"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    cfg = load_config()

    if args.cmd == "start":
        if ipc.is_running():
            print("Ordhjælp kører allerede")
            return 0
        from ordhjaelp import daemon

        daemon.run(cfg, hotkeys=not args.uden_genveje, tray=not args.uden_ikon)
        return 0

    if args.cmd == "hent-stemme":
        from ordhjaelp.tts.piper_engine import ensure_voice

        print(ensure_voice(cfg.voice, voices_dir()))
        return 0

    if args.cmd in ("installer", "afinstaller") and sys.platform == "win32":
        from ordhjaelp.platform.windows.install import WindowsAutostart

        autostart = WindowsAutostart()
        autostart.set_enabled(args.cmd == "installer" and args.autostart)
        print("Autostart ved login:", "til" if autostart.is_enabled() else "fra")
        return 0

    if args.cmd in ("installer", "afinstaller"):
        if not sys.platform.startswith("linux"):
            print("Kun understøttet på Linux og Windows indtil videre", file=sys.stderr)
            return 1
        from ordhjaelp.platform.linux import install

        paths = install.install(args.autostart) if args.cmd == "installer" else install.uninstall()
        for path in paths:
            print(("Installeret: " if args.cmd == "installer" else "Fjernet: ") + str(path))
        return 0

    if args.cmd == "sammenlign-modeller":
        from pathlib import Path

        from ordhjaelp.config import data_dir, whisper_dir
        from ordhjaelp.stt import compare

        if args.fil:
            audio = compare.load_wav(Path(args.fil))
        else:
            audio = compare.record_interactively()
            saved = data_dir() / "sammenlign.wav"
            compare.save_wav(audio, saved)
            print(f"Optagelsen er gemt i {saved}")
        compare.compare(audio, args.modeller or compare.DEFAULT_MODELS, whisper_dir())
        return 0

    if args.cmd == "status":
        running = ipc.is_running()
        print("Kører" if running else "Kører ikke", f"(indstillinger: {config_path()})")
        return 0 if running else 1

    request: ipc.Request = {"cmd": args.cmd.replace("-", "_")}
    if args.cmd == "sig":
        request["tekst"] = " ".join(args.tekst)
    try:
        reply = ipc.send(request)
    except ipc.CONNECT_ERRORS:
        print("Ordhjælp kører ikke. Start den med: ordhjaelp start", file=sys.stderr)
        return 1
    if not reply.get("ok"):
        print(reply.get("fejl", "Kunne ikke udføre kommandoen"), file=sys.stderr)
        return 1
    return 0


def _log_target() -> dict:
    """Uden konsol (fx Ordhjaelp.exe fra installeren) skrives loggen i en fil."""
    if sys.stderr is not None:
        return {}
    from logging.handlers import RotatingFileHandler

    from ordhjaelp.config import data_dir

    path = data_dir() / "ordhjaelp.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    return {"handlers": [handler]}


if __name__ == "__main__":
    sys.exit(main())
