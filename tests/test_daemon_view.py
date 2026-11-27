"""Knaplinjen behøver ikke et område til ikoner ved uret."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace  # noqa: E402

from ordhjaelp import daemon  # noqa: E402
from ordhjaelp.config import VIEW_TOOLBAR, VIEW_TRAY, Config  # noqa: E402
from ordhjaelp.ui import tray as tray_mod  # noqa: E402


class FakeTrayApp:
    started = 0
    tray_area = False

    def __init__(self, *args) -> None:
        pass

    @staticmethod
    def available() -> bool:
        return FakeTrayApp.tray_area

    def run(self) -> int:
        FakeTrayApp.started += 1
        return 0


def _run(monkeypatch, view: str) -> tuple[bool, Config]:
    FakeTrayApp.started = 0
    monkeypatch.setattr(tray_mod, "TrayApp", FakeTrayApp)
    cfg = Config()
    cfg.view = view
    ok = daemon._run_tray(None, None, None, {}, SimpleNamespace(config=cfg))
    return ok, cfg


def test_toolbar_starts_without_tray_area(monkeypatch) -> None:
    ok, cfg = _run(monkeypatch, VIEW_TOOLBAR)
    assert ok and FakeTrayApp.started == 1 and cfg.view == VIEW_TOOLBAR


def test_tray_view_falls_back_to_toolbar_without_tray_area(monkeypatch) -> None:
    """Kan skrivebordet ikke vise ikoner ved uret, bruges knaplinjen i stedet."""
    ok, cfg = _run(monkeypatch, VIEW_TRAY)
    assert ok and FakeTrayApp.started == 1 and cfg.view == VIEW_TOOLBAR


# -- beskeder til eleven og stemmen ---------------------------------------------
class _Speaker:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)


def test_messages_on_screen_when_chosen() -> None:
    shown, speaker = [], _Speaker()
    actions = {"besked": shown.append}
    tell = daemon._make_tell_user(Config(messages="skaerm"), speaker, actions)
    tell("Jeg hørte ikke noget")
    assert shown == ["Jeg hørte ikke noget"] and speaker.said == []


def test_messages_spoken_by_default() -> None:
    shown, speaker = [], _Speaker()
    tell = daemon._make_tell_user(Config(), speaker, {"besked": shown.append})
    tell("Hej")
    assert speaker.said == ["Hej"] and shown == []


def test_without_voice_and_screen_messages_fall_back_to_screen() -> None:
    # Kun diktering uden stemme: beskeden må ikke forsvinde i en stum stemme
    cfg = Config(usage="diktering", messages="skaerm")
    shown, speaker = [], _Speaker()
    actions = {}
    tell = daemon._make_tell_user(cfg, speaker, actions)
    tell("Før brugerfladen er klar")  # logges bare
    actions["besked"] = shown.append
    tell("Nu")
    assert shown == ["Nu"] and speaker.said == []


def test_voice_is_not_loaded_when_not_needed(monkeypatch) -> None:
    from ordhjaelp.tts.silent import SilentTTS

    def no_download(*_args):
        raise AssertionError("stemmen må ikke hentes")

    monkeypatch.setattr(daemon, "ensure_voice", no_download)
    tts = daemon._make_tts(Config(usage="diktering", messages="skaerm", speed=1.2))
    assert isinstance(tts, SilentTTS) and tts.speed == 1.2
    assert list(tts.synthesize("hej")) == []
