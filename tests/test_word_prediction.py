import json

from ordhjaelp.ordmotor import lexicon
from ordhjaelp.ordmotor.lexicon import Entry
from ordhjaelp.services import word_prediction
from ordhjaelp.services.word_prediction import WordPredictionService


def make(tmp_path, monkeypatch, learned=None):
    entries = [Entry("skole", 5.0), Entry("skal", 6.0), Entry("hvordan", 5.5)]
    monkeypatch.setattr(word_prediction, "load_entries", lambda path: entries)
    path = tmp_path / "egne_ord.json"
    if learned is not None:
        path.write_text(json.dumps(learned))
    svc = WordPredictionService(tmp_path / "ordliste.json", path)
    svc._load()
    return svc, path


def test_not_ready_gives_nothing(tmp_path) -> None:
    svc = WordPredictionService(tmp_path / "a.json", tmp_path / "b.json")
    assert svc.suggest("sk") == []


def test_suggests_after_load(tmp_path, monkeypatch) -> None:
    svc, _ = make(tmp_path, monkeypatch)
    assert svc.suggest("sgole")[0] == "skole"
    assert svc.suggest("vordan")[0] == "hvordan"


def test_learned_words_are_saved_and_loaded(tmp_path, monkeypatch) -> None:
    svc, path = make(tmp_path, monkeypatch)
    for _ in range(2):
        svc.learn("Mirai")
    svc.save()
    assert json.loads(path.read_text()) == {"Mirai": 2}
    again, _ = make(tmp_path, monkeypatch)
    assert again.suggest("Mir") == ["Mirai"]


def test_corrupt_learned_file_is_ignored(tmp_path, monkeypatch) -> None:
    svc, _ = make(tmp_path, monkeypatch, learned=["ikke", "en", "ordbog"])
    assert svc.suggest("sk")


def test_lexicon_cache_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lexicon, "build_entries", lambda: [Entry("hej", 5.0)])
    cache = tmp_path / "ordliste.json"
    assert lexicon.load_entries(cache) == [Entry("hej", 5.0)]
    monkeypatch.setattr(lexicon, "build_entries", lambda: [])  # bruges ikke: cache findes
    assert lexicon.load_entries(cache) == [Entry("hej", 5.0)]
