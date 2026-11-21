import pytest

from ordhjaelp.config import Config

DEFAULT_CONFIG = Config().to_toml()


def test_default_config_parses() -> None:
    cfg = Config.from_toml(DEFAULT_CONFIG)
    assert cfg.voice == "da_DK-talesyntese-medium"
    assert cfg.speed == 1.0
    assert cfg.hotkeys == {
        "laes": "CTRL+ALT+L",
        "stop": "CTRL+ALT+S",
        "dikter": "CTRL+ALT+D",
        "skaerm": "CTRL+ALT+B",
    }
    assert cfg.dictation_enabled is True
    assert cfg.dictation_model == "dansk-hurtig"


def test_partial_config_keeps_defaults() -> None:
    cfg = Config.from_toml('[oplaesning]\ntempo = 0.8\n[genveje]\nlaes = "META+R"\n')
    assert cfg.speed == 0.8
    assert cfg.voice == "da_DK-talesyntese-medium"
    assert cfg.hotkeys == {
        "laes": "META+R",
        "stop": "CTRL+ALT+S",
        "dikter": "CTRL+ALT+D",
        "skaerm": "CTRL+ALT+B",
    }


def test_invalid_speed_rejected() -> None:
    with pytest.raises(ValueError):
        Config.from_toml("[oplaesning]\ntempo = 0\n")


def test_model_names_resolve_via_catalog() -> None:
    from ordhjaelp.stt.whisper_engine import resolve_model

    assert resolve_model("dansk-hurtig") == "lucasw89/whisper-small-danish-ct2-int8"
    assert resolve_model("hurtig") == "small"
    assert resolve_model("noget/andet") == "noget/andet"
    assert resolve_model("da_DK-talesyntese-medium") == "da_DK-talesyntese-medium"  # ikke tale
