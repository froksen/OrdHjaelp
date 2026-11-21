from pathlib import Path

import pytest

from ordhjaelp.ordmotor.lexicon import load_entries
from ordhjaelp.ordmotor.phonetic import danish_key
from ordhjaelp.ordmotor.predictor import Predictor

CORPUS = Path(__file__).with_name("fejlkorpus.tsv")


def corpus() -> list[tuple[str, str]]:
    rows = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            typed, expected = line.split("\t")
            rows.append((typed, expected))
    return rows


@pytest.fixture(scope="module")
def predictor(tmp_path_factory) -> Predictor:
    return Predictor(load_entries(tmp_path_factory.mktemp("ord") / "ordliste.json"))


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("sgole", "skole"),
        ("vordan", "hvordan"),
        ("jem", "hjem"),
        ("man", "mand"),
        ("dejli", "dejlig"),
    ],
)
def test_sounds_alike(a: str, b: str) -> None:
    assert danish_key(a) == danish_key(b)


def test_error_corpus_hit_rate(predictor: Predictor) -> None:
    rows = corpus()
    misses = []
    top1 = 0
    for typed, expected in rows:
        words = [s.word.lower() for s in predictor.suggest(typed, n=5)]
        if words[:1] == [expected]:
            top1 += 1
        if expected not in words:
            misses.append(f"{typed} → {expected}: {words}")
    hit_rate = 1 - len(misses) / len(rows)
    print(f"\nTop-1: {top1}/{len(rows)}  Top-5: {len(rows) - len(misses)}/{len(rows)}")
    print("\n".join(misses))
    assert hit_rate >= 0.85, "\n".join(misses)


def test_no_english_or_numbers(predictor: Predictor) -> None:
    for typed in ("th", "yo", "an", "1"):
        words = [s.word for s in predictor.suggest(typed)]
        assert "the" not in words and "you" not in words and "and" not in words


def test_names_keep_capital(predictor: Predictor) -> None:
    assert "København" in [s.word for s in predictor.suggest("køben")]


def test_follows_typed_capital(predictor: Predictor) -> None:
    assert predictor.suggest("Sko")[0].word[0] == "S"


def test_learning_new_word() -> None:
    p = Predictor([])
    p.learn("Mirai")
    assert not p.knows("Mirai")
    p.learn("Mirai")
    assert [s.word for s in p.suggest("Mir")] == ["Mirai"]
