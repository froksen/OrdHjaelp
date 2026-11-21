import sys

import pytest

from ordhjaelp import ipc


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(ipc, "config_dir", lambda: tmp_path / "cfg")
    return tmp_path


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-socket-sti")
def test_roundtrip(isolated) -> None:
    calls = []

    def handler(req):
        calls.append(req)
        return {"ok": True, "ekko": req.get("tekst")}

    assert not ipc.is_running()
    server = ipc.Server(handler)
    server.start()
    try:
        assert ipc.is_running()
        assert ipc.send({"cmd": "sig", "tekst": "hej"}) == {"ok": True, "ekko": "hej"}
        with pytest.raises(RuntimeError):
            ipc.Server(handler)  # kun én instans ad gangen
    finally:
        server.close()
    assert (isolated / "cfg" / "ipc.key").stat().st_mode & 0o777 == 0o600


def test_wrong_key_rejected(isolated) -> None:
    server = ipc.Server(lambda req: {"ok": True})
    server.start()
    try:
        (isolated / "cfg" / "ipc.key").write_bytes(b"forkert")
        assert not ipc.is_running()
    finally:
        server.close()
