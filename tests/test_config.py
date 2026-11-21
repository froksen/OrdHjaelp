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
        "laes_ord": "CTRL+ALT+1",
        "laes_saetning": "CTRL+ALT+2",
        "laes_herfra": "CTRL+ALT+3",
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
        "laes_ord": "CTRL+ALT+1",
        "laes_saetning": "CTRL+ALT+2",
        "laes_herfra": "CTRL+ALT+3",
    }


def test_invalid_speed_rejected() -> None:
    with pytest.raises(ValueError):
        Config.from_toml("[oplaesning]\ntempo = 0\n")


def test_model_aliases_are_ready_made_repos() -> None:
    from ordhjaelp.stt.whisper_engine import MODEL_ALIASES, resolve_model

    assert resolve_model("dansk-hurtig") == "lucasw89/whisper-small-danish-ct2-int8"
    assert resolve_model("noget/andet") == "noget/andet"
    assert all(v for v in MODEL_ALIASES.values())


def test_roundtrip_keeps_all_values() -> None:
    cfg = Config(
        speed=0.85,
        use_clipboard_fallback=True,
        dictation_enabled=False,
        dictation_model="dansk-turbo",
    )
    cfg.show_icons["skaerm"] = False
    cfg.hotkeys["laes"] = "META+L"
    again = Config.from_toml(cfg.to_toml())
    assert again == cfg


def test_strings_with_quotes_are_escaped() -> None:
    cfg = Config(voice='mærkelig "stemme"')
    assert Config.from_toml(cfg.to_toml()).voice == 'mærkelig "stemme"'


def test_read_at_pointer_is_off_by_default_and_roundtrips() -> None:
    assert Config.from_toml(DEFAULT_CONFIG).read_at_pointer is False
    assert Config.from_toml(Config(read_at_pointer=True).to_toml()).read_at_pointer is True
    assert Config.from_toml("[oplaesning]\nlaes_under_musen = true\n").read_at_pointer
