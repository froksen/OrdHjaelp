import pytest

from ordhjaelp.textutil import normalize_for_speech


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hej   med\n dig", "Hej med dig"),
        ("ord-\ndeling", "orddeling"),
        ("ord- \n  deling", "orddeling"),
        ("EU-\nLande", "EU-Lande"),
        ("side 2-\n3", "side 2-3"),
        ("blød­bindestreg", "blødbindestreg"),
        ("linje1\r\nlinje2", "linje1 linje2"),
        ("   \n\t ", ""),
        ("Æble-\nøen", "Æbleøen"),
    ],
)
def test_normalize_for_speech(raw: str, expected: str) -> None:
    assert normalize_for_speech(raw) == expected
