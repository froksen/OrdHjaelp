import pytest

from ordhjaelp.services.pointer_read import (
    MSG_NOTHING,
    PointerReadService,
    from_here,
    sentence_at,
    word_at,
)

TEXT = "Hunden løb hjem. Den var træt! Så sov den."


def pos(word: str, text: str = TEXT) -> int:
    return text.index(word) + 1  # musen står inde i ordet


def test_word_at() -> None:
    assert word_at(TEXT, pos("løb")) == "løb"
    assert word_at(TEXT, 0) == "Hunden"
    assert word_at(TEXT, pos("hjem")) == "hjem"  # uden punktum


def test_word_at_handles_hyphen_and_apostrophe() -> None:
    assert word_at("en EU-borger her", 5) == "EU-borger"
    assert word_at("Peters bil", 2) == "Peters"


def test_word_at_between_words_is_empty() -> None:
    assert word_at("to  ord", 3) == ""
    assert word_at("", 0) == ""


def test_sentence_at() -> None:
    assert sentence_at(TEXT, pos("løb")) == "Hunden løb hjem."
    assert sentence_at(TEXT, pos("træt")) == "Den var træt!"
    assert sentence_at(TEXT, pos("sov")) == "Så sov den."


def test_sentence_at_does_not_split_on_abbreviation_like_numbers() -> None:
    text = "Den 3.5 meter lange båd. Næste."
    assert sentence_at(text, pos("båd", text)) == "Den 3.5 meter lange båd."


def test_from_here_starts_at_word_start() -> None:
    assert from_here(TEXT, pos("var")) == "var træt! Så sov den."
    assert from_here(TEXT, 0) == TEXT


@pytest.mark.parametrize("offset", [-1, 999])
def test_out_of_range_is_empty(offset: int) -> None:
    assert word_at(TEXT, offset) == ""
    assert sentence_at(TEXT, offset) == ""
    assert from_here(TEXT, offset) == ""


class FakeProvider:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.units: list[str] = []

    def text_at_pointer(self, unit: str) -> str | None:
        self.units.append(unit)
        return self.text


def test_service_reads_text_at_pointer() -> None:
    said: list[str] = []
    svc = PointerReadService(FakeProvider("skole"), said.append)
    assert svc.read("ord")
    assert said == ["skole"]


def test_service_tells_when_nothing_found() -> None:
    said: list[str] = []
    svc = PointerReadService(FakeProvider(None), said.append)
    assert not svc.read("saetning")
    assert said == [MSG_NOTHING]


def test_service_rejects_unknown_unit() -> None:
    svc = PointerReadService(FakeProvider("x"), lambda _t: None)
    with pytest.raises(ValueError):
        svc.read("bogstav")


def test_service_survives_provider_errors() -> None:
    class Broken:
        def text_at_pointer(self, unit: str) -> str | None:
            raise RuntimeError("D-Bus er væk")

    said: list[str] = []
    assert not PointerReadService(Broken(), said.append).read("ord")
    assert said == [MSG_NOTHING]
