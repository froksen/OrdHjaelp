import pytest

from ordhjaelp.config import DEFAULT_CONFIG, Config


def test_default_config_parses() -> None:
    cfg = Config.from_toml(DEFAULT_CONFIG)
    assert cfg.voice == "da_DK-talesyntese-medium"
    assert cfg.speed == 1.0
    assert cfg.hotkeys == {"laes": "CTRL+ALT+L", "stop": "CTRL+ALT+S"}


def test_partial_config_keeps_defaults() -> None:
    cfg = Config.from_toml('[oplaesning]\ntempo = 0.8\n[genveje]\nlaes = "META+R"\n')
    assert cfg.speed == 0.8
    assert cfg.voice == "da_DK-talesyntese-medium"
    assert cfg.hotkeys == {"laes": "META+R", "stop": "CTRL+ALT+S"}


def test_invalid_speed_rejected() -> None:
    with pytest.raises(ValueError):
        Config.from_toml("[oplaesning]\ntempo = 0\n")
