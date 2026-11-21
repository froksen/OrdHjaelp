"""Lokal kommunikation mellem kommandolinjen/brugerfladen og tjenesten.

Bygger på multiprocessing.connection, som bruger en Unix-socket på Linux/macOS
og en named pipe på Windows – uden ekstra afhængigheder.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import tempfile
import threading
from collections.abc import Callable
from multiprocessing import AuthenticationError
from multiprocessing.connection import Client, Listener
from pathlib import Path
from typing import Any

from ordhjaelp.config import config_dir

log = logging.getLogger(__name__)

Request = dict[str, Any]
Response = dict[str, Any]

# Fejl der betyder "kunne ikke få kontakt til tjenesten"
CONNECT_ERRORS = (OSError, EOFError, TimeoutError, AuthenticationError)


def address() -> str:
    if sys.platform == "win32":
        return rf"\\.\pipe\ordhjaelp-{os.getlogin()}"
    runtime = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return str(Path(runtime) / "ordhjaelp.sock")


def _authkey() -> bytes:
    """Hemmelig nøgle, så kun brugerens egne processer kan styre tjenesten."""
    path = config_dir() / "ipc.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(os.urandom(32))
    return path.read_bytes()


class Server:
    def __init__(self, handler: Callable[[Request], Response]) -> None:
        self._handler = handler
        addr = address()
        if sys.platform != "win32" and os.path.exists(addr):
            if is_running():
                raise RuntimeError("Ordhjælp kører allerede")
            os.unlink(addr)  # efterladt fra et nedbrud
        self._listener = Listener(addr, authkey=_authkey())
        self._thread = threading.Thread(target=self._serve, daemon=True, name="ipc")

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._listener.close()

    def _serve(self) -> None:
        while True:
            try:
                conn = self._listener.accept()
            except AuthenticationError:
                log.warning("Afviste forbindelse med forkert nøgle")
                continue
            except OSError:
                return  # lukket
            except Exception:
                log.exception("Fejl ved ny forbindelse")
                continue
            with conn:
                try:
                    request = conn.recv()
                    conn.send(self._handler(request))
                except Exception as exc:
                    log.exception("Fejl i IPC-kald")
                    with contextlib.suppress(OSError):
                        conn.send({"ok": False, "fejl": str(exc)})


def send(request: Request, timeout: float = 5.0) -> Response:
    with Client(address(), authkey=_authkey()) as conn:
        conn.send(request)
        if not conn.poll(timeout):
            raise TimeoutError("Ordhjælp svarede ikke")
        return conn.recv()


def is_running() -> bool:
    try:
        return send({"cmd": "ping"}, timeout=1).get("ok", False)
    except CONNECT_ERRORS:
        return False
