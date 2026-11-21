"""Indstillinger og stier.

Alle stier går gennem platformdirs, så de passer på Linux, Windows og macOS.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

APP_NAME = "ordhjaelp"
APP_ID = "dk.ordhjaelp.Ordhjaelp"


def config_dir() -> Path:
    return Path(user_config_dir(APP_NAME))


def data_dir() -> Path:
    return Path(user_data_dir(APP_NAME))


def voices_dir() -> Path:
    return data_dir() / "stemmer"


def whisper_dir() -> Path:
    return data_dir() / "talegenkendelse"


DEFAULT_CONFIG = """\
# Ordhjælp – indstillinger

[oplaesning]
# Piper-stemme. Se https://huggingface.co/rhasspy/piper-voices
stemme = "da_DK-talesyntese-medium"
# Taletempo: 1.0 er normalt, 0.8 er langsommere, 1.3 er hurtigere.
tempo = 1.0
# Brug udklipsholderen (Ctrl+C), hvis der ikke er markeret noget tekst.
# Slået fra som standard, da det kan læse gammel, kopieret tekst op.
brug_udklipsholder = false

[diktering]
aktiv = true
# Talegenkendelse (hentes automatisk første gang):
#   "dansk-hurtig" – dansk, hurtig (standard)      "dansk-turbo" – dansk, mere præcis, langsommere
#   "dansk-stor"   – dansk (CoRal røst), langsom   "hurtig"/"turbo" – generelle modeller
model = "dansk-hurtig"

[genveje]
# Ønskede tastaturgenveje. På KDE/GNOME kan de ændres i systemindstillingerne.
laes = "CTRL+ALT+L"
stop = "CTRL+ALT+S"
dikter = "CTRL+ALT+D"
skaerm = "CTRL+ALT+B"
"""


@dataclass
class Config:
    voice: str = "da_DK-talesyntese-medium"
    speed: float = 1.0
    use_clipboard_fallback: bool = False
    dictation_enabled: bool = True
    dictation_model: str = "dansk-hurtig"
    hotkeys: dict[str, str] = field(
        default_factory=lambda: {
            "laes": "CTRL+ALT+L",
            "stop": "CTRL+ALT+S",
            "dikter": "CTRL+ALT+D",
            "skaerm": "CTRL+ALT+B",
        }
    )

    @classmethod
    def from_toml(cls, text: str) -> Config:
        raw = tomllib.loads(text)
        cfg = cls()
        reading = raw.get("oplaesning", {})
        cfg.voice = str(reading.get("stemme", cfg.voice))
        cfg.speed = float(reading.get("tempo", cfg.speed))
        if cfg.speed <= 0:
            raise ValueError("tempo skal være større end 0")
        cfg.use_clipboard_fallback = bool(
            reading.get("brug_udklipsholder", cfg.use_clipboard_fallback)
        )
        dictation = raw.get("diktering", {})
        cfg.dictation_enabled = bool(dictation.get("aktiv", cfg.dictation_enabled))
        cfg.dictation_model = str(dictation.get("model", cfg.dictation_model))
        cfg.hotkeys.update({str(k): str(v) for k, v in raw.get("genveje", {}).items()})
        return cfg


def config_path() -> Path:
    return config_dir() / "config.toml"


def load_config() -> Config:
    """Indlæs indstillinger. Første gang skrives en standardfil."""
    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return Config.from_toml(path.read_text(encoding="utf-8"))
