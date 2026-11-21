"""Det, Windows-installeren (det pakkede Ordhjaelp.exe) afhænger af."""

import sys

from ordhjaelp import bundled
from ordhjaelp.daemon import restart_command
from ordhjaelp.ocr import tesseract
from ordhjaelp.ordmotor import lexicon
from ordhjaelp.platform.windows.install import start_command


def _fake_install(tmp_path, monkeypatch):  # noqa: ANN001, ANN202
    exe = tmp_path / "Ordhjaelp.exe"
    exe.write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return exe


def test_autostart_starts_the_installed_program() -> None:
    cmd = start_command(executable=r"C:\Ordhjaelp\Ordhjaelp.exe", frozen=True)
    assert cmd == r'"C:\Ordhjaelp\Ordhjaelp.exe" start'


def test_restart_runs_the_installed_program_with_same_arguments() -> None:
    exe = r"C:\Ordhjaelp\Ordhjaelp.exe"
    assert restart_command(exe, ["start"], frozen=True) == [exe, "start"]
    assert restart_command("python", ["start"], frozen=False) == [
        "python",
        "-m",
        "ordhjaelp",
        "start",
    ]


def test_no_bundled_tools_outside_installer() -> None:
    assert bundled.tools_dir() is None
    assert bundled.tool("hunspell") is None


def test_bundled_hunspell_uses_its_own_dictionary(tmp_path, monkeypatch) -> None:
    _fake_install(tmp_path, monkeypatch)
    hunspell = tmp_path / "tools" / "hunspell" / "hunspell.exe"
    hunspell.parent.mkdir(parents=True)
    hunspell.write_text("")
    assert lexicon.hunspell_command() == [
        str(hunspell),
        "-d",
        str(hunspell.parent / "da_DK"),
    ]


def test_bundled_tesseract_uses_its_own_language_data(tmp_path, monkeypatch) -> None:
    _fake_install(tmp_path, monkeypatch)
    exe = tmp_path / "tools" / "tesseract" / "tesseract.exe"
    (exe.parent / "tessdata").mkdir(parents=True)
    exe.write_text("")
    assert tesseract.find_tesseract() == str(exe)
    assert tesseract._tessdata_args(str(exe)) == ["--tessdata-dir", str(exe.parent / "tessdata")]


def test_log_goes_to_file_without_console(tmp_path, monkeypatch) -> None:
    from ordhjaelp import cli, config

    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    handlers = cli._log_target()["handlers"]
    try:
        assert handlers[0].baseFilename == str(tmp_path / "ordhjaelp.log")
    finally:
        handlers[0].close()


def test_word_list_without_hunspell_is_rebuilt_when_hunspell_arrives(tmp_path, monkeypatch) -> None:
    import json

    cache = tmp_path / "ordliste.json"
    cache.write_text(
        json.dumps({"version": lexicon.LEXICON_VERSION, "hunspell": False, "words": [["hus", 5]]}),
        encoding="utf-8",
    )
    built = [lexicon.Entry("skole", 5.0)]
    monkeypatch.setattr(lexicon, "build_entries", lambda: built)
    monkeypatch.setattr(lexicon, "hunspell_command", lambda: None)
    assert [e.word for e in lexicon.load_entries(cache)] == ["hus"]  # stadig uden Hunspell
    monkeypatch.setattr(lexicon, "hunspell_command", lambda: ["hunspell"])
    assert lexicon.load_entries(cache) == built
    assert json.loads(cache.read_text(encoding="utf-8"))["hunspell"] is True
