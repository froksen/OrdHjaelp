import pytest

from ordhjaelp.config import Config
from ordhjaelp.daemon import _read_while_typing


class FakeService:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)
        return True


@pytest.mark.parametrize(
    ("word_on", "sentence_on", "req", "expected"),
    [
        (False, False, {"ord": "hej", "saetning": None}, []),
        (True, False, {"ord": "hej", "saetning": None}, ["hej"]),
        (False, True, {"ord": "hej", "saetning": None}, []),
        (False, True, {"ord": "dig", "saetning": "Hej med dig."}, ["Hej med dig."]),
        # Begge slået til: ved punktum læses kun sætningen (ikke også det sidste ord)
        (True, True, {"ord": "dig", "saetning": "Hej med dig."}, ["Hej med dig."]),
        # Kun ord slået til: punktum efter et ord læser ordet
        (True, False, {"ord": "dig", "saetning": "Hej med dig."}, ["dig"]),
        (True, True, {"ord": None, "saetning": None}, []),
    ],
)
def test_read_while_typing(word_on, sentence_on, req, expected) -> None:
    cfg = Config(read_word_on_space=word_on, read_sentence_on_period=sentence_on)
    svc = FakeService()
    _read_while_typing(cfg, svc, req)
    assert svc.said == expected


def test_settings_roundtrip() -> None:
    cfg = Config(read_word_on_space=True, read_sentence_on_period=True)
    assert Config.from_toml(cfg.to_toml()) == cfg
