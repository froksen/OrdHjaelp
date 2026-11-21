from ordhjaelp.ocr.tesseract import clean_ocr_text
from ordhjaelp.services.screen_read import (
    MSG_ERROR,
    MSG_NO_OCR,
    MSG_NO_TEXT,
    OcrUnavailable,
    ScreenReadService,
)


class FakeCapture:
    def __init__(self, fail=False):
        self.fail = fail

    def capture(self):
        if self.fail:
            raise RuntimeError("portal afvist")
        return b"PNG"


class FakeOCR:
    def __init__(self, text="", exc=None):
        self.text, self.exc = text, exc

    def recognize(self, png):
        if self.exc:
            raise self.exc
        return self.text


def make(ocr=None, capture=None):
    said, stopped = [], []
    svc = ScreenReadService(
        capture or FakeCapture(), ocr or FakeOCR(), said.append, lambda: stopped.append(1)
    )
    return svc, said, stopped


def test_screenshot_stops_reading_first() -> None:
    svc, said, stopped = make()
    assert svc.take_screenshot() == b"PNG"
    assert stopped == [1] and said == []


def test_screenshot_failure_tells_user() -> None:
    svc, said, _ = make(capture=FakeCapture(fail=True))
    assert svc.take_screenshot() is None
    assert said == [MSG_ERROR]


def test_text_is_read_aloud() -> None:
    svc, said, _ = make(FakeOCR("  Hej verden  "))
    assert svc.read_image(b"x") == "Hej verden"
    assert said == ["Hej verden"]


def test_no_text_found() -> None:
    svc, said, _ = make(FakeOCR(""))
    svc.read_image(b"x")
    assert said == [MSG_NO_TEXT]


def test_ocr_missing() -> None:
    svc, said, _ = make(FakeOCR(exc=OcrUnavailable("mangler")))
    svc.read_image(b"x")
    assert said == [MSG_NO_OCR]


def test_ocr_crash() -> None:
    svc, said, _ = make(FakeOCR(exc=RuntimeError("boom")))
    svc.read_image(b"x")
    assert said == [MSG_ERROR]


def test_clean_ocr_text_drops_noise_lines() -> None:
    raw = "Overskrift\n\n|\n— \nFørste linje med tekst\n.\nAnden linje\n"
    assert clean_ocr_text(raw) == "Overskrift\nFørste linje med tekst\nAnden linje"
