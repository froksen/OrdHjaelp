"""Indstillinger og stier.

Alle stier går gennem platformdirs, så de passer på Linux, Windows og macOS.
"""

from __future__ import annotations

import json
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


def lexicon_path() -> Path:
    return data_dir() / "ordliste.json"


def learned_words_path() -> Path:
    return data_dir() / "egne_ord.json"


def voices_dir() -> Path:
    return data_dir() / "stemmer"


def whisper_dir() -> Path:
    return data_dir() / "talegenkendelse"


@dataclass
class Config:
    voice: str = "da_DK-talesyntese-medium"
    speed: float = 1.0
    use_clipboard_fallback: bool = False
    read_word_on_space: bool = False
    read_sentence_on_period: bool = False
    dictation_enabled: bool = True
    dictation_model: str = "dansk-hurtig"
    prediction_enabled: bool = True
    hotkeys: dict[str, str] = field(
        default_factory=lambda: {
            "laes": "CTRL+ALT+L",
            "stop": "CTRL+ALT+S",
            "dikter": "CTRL+ALT+D",
            "skaerm": "CTRL+ALT+B",
        }
    )
    # Hvilke ikoner der vises ved uret (læs op-ikonet vises altid – det har menuen)
    show_icons: dict[str, bool] = field(default_factory=lambda: {"dikter": True, "skaerm": True})

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
        cfg.read_word_on_space = bool(reading.get("laes_ord_ved_mellemrum", False))
        cfg.read_sentence_on_period = bool(reading.get("laes_saetning_ved_punktum", False))
        dictation = raw.get("diktering", {})
        cfg.dictation_enabled = bool(dictation.get("aktiv", cfg.dictation_enabled))
        cfg.dictation_model = str(dictation.get("model", cfg.dictation_model))
        prediction = raw.get("ordforslag", {})
        cfg.prediction_enabled = bool(prediction.get("aktiv", cfg.prediction_enabled))
        cfg.hotkeys.update({str(k): str(v) for k, v in raw.get("genveje", {}).items()})
        cfg.show_icons.update({str(k): bool(v) for k, v in raw.get("ikoner", {}).items()})
        return cfg

    def to_toml(self) -> str:
        """Hele indstillingsfilen med forklarende kommentarer."""

        def s(value: str) -> str:
            return json.dumps(value, ensure_ascii=False)  # gyldig TOML-streng

        def b(value: bool) -> str:
            return "true" if value else "false"

        hotkeys = "\n".join(f"{k} = {s(v)}" for k, v in self.hotkeys.items())
        icons = "\n".join(f"{k} = {b(v)}" for k, v in self.show_icons.items())
        return f"""\
# Ordhjælp – indstillinger
# Kan også ændres via højreklik på det blå ikon → Indstillinger.

[oplaesning]
# Piper-stemme. Se https://huggingface.co/rhasspy/piper-voices
stemme = {s(self.voice)}
# Taletempo: 1.0 er normalt, 0.8 er langsommere, 1.3 er hurtigere.
tempo = {round(self.speed, 2)}
# Brug udklipsholderen (Ctrl+C), hvis der ikke er markeret noget tekst.
# Slået fra som standard, da det kan læse gammel, kopieret tekst op.
brug_udklipsholder = {b(self.use_clipboard_fallback)}
# Læs mens du skriver (kræver ordforslag/IBus):
laes_ord_ved_mellemrum = {b(self.read_word_on_space)}
laes_saetning_ved_punktum = {b(self.read_sentence_on_period)}

[diktering]
aktiv = {b(self.dictation_enabled)}
# Talegenkendelse (hentes automatisk første gang):
#   "dansk-hurtig" – dansk, hurtig (standard)      "dansk-turbo" – dansk, mere præcis, langsommere
#   "dansk-stor"   – dansk (CoRal røst), langsom   "hurtig"/"turbo" – generelle modeller
model = {s(self.dictation_model)}

[ordforslag]
# Forslag mens der skrives (kræver IBus – se README)
aktiv = {b(self.prediction_enabled)}

[ikoner]
# Vis ikoner ved uret (dikter = mikrofon, skaerm = læs fra skærmen)
{icons}

[genveje]
# Ønskede tastaturgenveje. På KDE/GNOME kan de ændres i systemindstillingerne.
{hotkeys}
"""


def config_path() -> Path:
    return config_dir() / "config.toml"


def load_config() -> Config:
    """Indlæs indstillinger. Første gang skrives en standardfil."""
    path = config_path()
    if not path.exists():
        save_config(Config())
    return Config.from_toml(path.read_text(encoding="utf-8"))


def save_config(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(cfg.to_toml(), encoding="utf-8")
    tmp.replace(path)  # atomisk: aldrig en halvt skrevet fil
