"""Integrationstest af IBus-motoren mod en privat IBus-instans.

Testen er helt isoleret: egen ibus-daemon og egen lille Ordhjælp-tjeneste
(XDG_RUNTIME_DIR/XDG_CONFIG_HOME peger på en midlertidig mappe), så den
hverken ændrer brugerens tastatur eller "lærer" ord i brugerens ordliste.

Kræver ibus-daemon og systemets python3-gobject. Køres med:
    ORDHJAELP_IBUS_TEST=1 pytest tests/integration
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "src/ordhjaelp/platform/linux/ibus_engine.py"
CLIENT = Path(__file__).with_name("ibus_client.py")

pytestmark = pytest.mark.skipif(
    not os.environ.get("ORDHJAELP_IBUS_TEST") or shutil.which("ibus-daemon") is None,
    reason="sæt ORDHJAELP_IBUS_TEST=1 (kræver ibus-daemon)",
)


@pytest.fixture
def isolated_service(tmp_path, monkeypatch):
    """En Ordhjælp-tjeneste med den rigtige ordmotor, men uden at gemme noget."""
    from ordhjaelp import ipc
    from ordhjaelp.config import lexicon_path
    from ordhjaelp.ordmotor.lexicon import load_entries
    from ordhjaelp.ordmotor.predictor import Predictor

    predictor = Predictor(load_entries(lexicon_path()))  # læser kun brugerens ordliste-cache
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    learned: list[str] = []
    written: list[dict] = []

    def handle(req):
        if req.get("cmd") == "skrevet":
            written.append({"ord": req.get("ord"), "saetning": req.get("saetning")})
        if req.get("cmd") == "forslag":
            return {"ok": True, "forslag": [s.word for s in predictor.suggest(req["ord"])]}
        if req.get("cmd") == "laer":
            learned.append(req["ord"])
        return {"ok": True}

    server = ipc.Server(handle)
    server.start()
    yield learned, written
    server.close()


def test_typing_through_ibus(tmp_path, isolated_service) -> None:
    env = dict(os.environ, IBUS_ADDRESS=f"unix:path={tmp_path}/ibus.sock")
    daemon = subprocess.Popen(
        ["ibus-daemon", "--panel=disable", "--config=disable", f"--address={env['IBUS_ADDRESS']}"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(300):  # vent til ibus-daemon lytter
            if (tmp_path / "ibus.sock").exists():
                break
            time.sleep(0.1)
        engine = subprocess.Popen(["/usr/bin/python3", str(ENGINE)], env=env)
        try:
            out = subprocess.run(
                ["/usr/bin/python3", str(CLIENT)],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            ).stdout
        finally:
            engine.terminate()
    finally:
        daemon.terminate()
    assert (
        "skrevet: ['sgole', 'skole', 'hvordan', 'fodboldspiller', 'hej', 'København', "
        "'Jeg', 'leger']" in out
    )
    time.sleep(0.5)
    learned, written = isolated_service
    # Motoren beder tjenesten om at huske de ord, der blev skrevet
    assert "skole" in learned and "København" in learned
    # … og melder færdige ord og sætninger (til "læs mens du skriver")
    assert {"ord": "Jeg", "saetning": None} in written
    last = written[-1]
    assert last["ord"] == "leger" and last["saetning"].endswith("København Jeg leger.")
