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

# Hvor knapperne vises: en lille knaplinje på skærmen eller ikoner ved uret
VIEW_TOOLBAR = "knaplinje"
VIEW_TRAY = "ikoner"
VIEWS = (VIEW_TOOLBAR, VIEW_TRAY)

# Hvad Ordhjælp bruges til. Vælges ved første start og kan ændres i indstillingerne.
# Det fravalgte bliver ikke slettet: vælger man "alt" igen, er de gamle valg der stadig.
USAGE_ALL = "alt"  # alle funktioner
USAGE_READ = "oplaesning"  # kun læs op (også læs fra skærmen, PDF og læs mens du skriver)
USAGE_DICTATION = "diktering"  # kun diktering
USAGES = (USAGE_ALL, USAGE_READ, USAGE_DICTATION)

# Beskeder til eleven fra diktering (fx "Jeg hørte ikke noget"): læst op eller på skærmen.
# Læst op kræver stemmen. På skærmen kan man med kun diktering slippe for at hente den.
MESSAGES_SPEAK = "oplaes"
MESSAGES_SCREEN = "skaerm"
MESSAGES = (MESSAGES_SPEAK, MESSAGES_SCREEN)

# Knapperne, og hvilken slags brug de hører til
READING_BUTTONS = ("laes", "skaerm", "pdf")
DICTATION_BUTTONS = ("dikter",)


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
    read_on_select: bool = False
    read_at_pointer: bool = False
    dictation_enabled: bool = True
    dictation_model: str = "dansk-hurtig"
    prediction_enabled: bool = True
    hotkeys: dict[str, str] = field(
        default_factory=lambda: {
            "laes": "CTRL+ALT+L",
            "stop": "CTRL+ALT+S",
            "dikter": "CTRL+ALT+D",
            "skaerm": "CTRL+ALT+B",
            "laes_ord": "CTRL+ALT+1",
            "laes_saetning": "CTRL+ALT+2",
            "laes_herfra": "CTRL+ALT+3",
        }
    )
    # Hvilke knapper der vises ud over læs op: i knaplinjen eller som ikoner ved uret.
    # "pdf" styrer både knappen og menupunktet "Gør en PDF søgbar".
    show_icons: dict[str, bool] = field(
        default_factory=lambda: {"dikter": True, "skaerm": True, "pdf": True}
    )
    view: str = VIEW_TOOLBAR
    usage: str = USAGE_ALL
    messages: str = MESSAGES_SPEAK
    # Har eleven været gennem velkomstguiden? Nye brugere: nej. Gamle indstillingsfiler
    # uden [brug] er fra før guiden fandtes, og de brugere skal ikke se den igen.
    welcome_done: bool = False

    # -- det, der faktisk er slået til, når brugen er valgt ---------------------
    @property
    def uses_reading(self) -> bool:
        return self.usage != USAGE_DICTATION

    @property
    def uses_dictation(self) -> bool:
        return self.usage != USAGE_READ

    @property
    def dictation_active(self) -> bool:
        return self.dictation_enabled and self.uses_dictation

    @property
    def prediction_active(self) -> bool:
        """Ordforslag hører kun med, når alle funktioner er valgt."""
        return self.prediction_enabled and self.usage == USAGE_ALL

    @property
    def read_on_select_active(self) -> bool:
        return self.read_on_select and self.uses_reading

    @property
    def read_at_pointer_active(self) -> bool:
        return self.read_at_pointer and self.uses_reading

    @property
    def read_word_active(self) -> bool:
        return self.read_word_on_space and self.uses_reading

    @property
    def read_sentence_active(self) -> bool:
        return self.read_sentence_on_period and self.uses_reading

    @property
    def speaks_messages(self) -> bool:
        """Læses beskeder fra diktering op (ellers vises de på skærmen)?"""
        return self.messages == MESSAGES_SPEAK

    @property
    def needs_voice(self) -> bool:
        """Skal stemmen hentes? Kun diktering med beskeder på skærmen klarer sig uden."""
        return self.uses_reading or self.speaks_messages

    def button_allowed(self, name: str) -> bool:
        """Hører knappen med til den valgte brug?"""
        if name in DICTATION_BUTTONS:
            return self.uses_dictation
        if name in READING_BUTTONS:
            return self.uses_reading
        return True

    @property
    def typing_help_enabled(self) -> bool:
        """Ordforslag eller læs mens du skriver – begge kræver tastaturdelen (IBus på Linux)."""
        return self.prediction_active or self.read_word_active or self.read_sentence_active

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
        cfg.read_on_select = bool(reading.get("laes_ved_markering", False))
        cfg.read_at_pointer = bool(reading.get("laes_under_musen", False))
        dictation = raw.get("diktering", {})
        cfg.dictation_enabled = bool(dictation.get("aktiv", cfg.dictation_enabled))
        cfg.dictation_model = str(dictation.get("model", cfg.dictation_model))
        prediction = raw.get("ordforslag", {})
        cfg.prediction_enabled = bool(prediction.get("aktiv", cfg.prediction_enabled))
        # [pdf] soegbar (til og med version 0.4) viste kun menupunktet. Nu styrer [ikoner] pdf
        # både knappen og menupunktet, så den gamle indstilling læses ikke længere.
        cfg.hotkeys.update({str(k): str(v) for k, v in raw.get("genveje", {}).items()})
        icons = dict(raw.get("ikoner", {}))
        icons.pop("altid_synlige", None)  # fra version 0.2 (virkede ikke), er ikke et ikon
        cfg.show_icons.update({str(k): bool(v) for k, v in icons.items()})
        view = str(raw.get("visning", {}).get("knapper", cfg.view))
        cfg.view = view if view in VIEWS else VIEW_TOOLBAR
        usage = raw.get("brug", {})
        cfg.usage = str(usage.get("funktioner", cfg.usage))
        if cfg.usage not in USAGES:
            cfg.usage = USAGE_ALL
        cfg.messages = str(usage.get("beskeder", cfg.messages))
        if cfg.messages not in MESSAGES:
            cfg.messages = MESSAGES_SPEAK
        # Uden [brug] er filen fra før velkomstguiden: den er der ikke brug for igen
        cfg.welcome_done = bool(usage.get("velkommen_vist", "brug" not in raw))
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
# Kan også ændres under ⋯ i knaplinjen → Indstillinger
# (eller højreklik på det blå ikon, hvis knapperne vises som ikoner ved uret).

[brug]
# Hvad Ordhjælp bruges til: "alt" (alle funktioner), "oplaesning" (kun læs op)
# eller "diktering" (kun diktering). Det fravalgte gemmes og kommer igen med "alt".
funktioner = {s(self.usage)}
# Beskeder fra diktering (fx "Jeg hørte ikke noget"): "oplaes" (læses op med stemmen)
# eller "skaerm" (vises på skærmen)
beskeder = {s(self.messages)}
# Velkomstguiden vises ved første start
velkommen_vist = {b(self.welcome_done)}

[oplaesning]
# Piper-stemme. Se https://huggingface.co/rhasspy/piper-voices
stemme = {s(self.voice)}
# Taletempo: 1.0 er normalt, 0.8 er langsommere, 1.3 er hurtigere.
tempo = {round(self.speed, 2)}
# Brug udklipsholderen (Ctrl+C), hvis der ikke er markeret noget tekst.
# Slået fra som standard, da det kan læse gammel, kopieret tekst op.
brug_udklipsholder = {b(self.use_clipboard_fallback)}
# Læs mens du skriver (på Linux kræver det IBus):
laes_ord_ved_mellemrum = {b(self.read_word_on_space)}
laes_saetning_ved_punktum = {b(self.read_sentence_on_period)}
# Læs ved markering: læs op, så snart der markeres tekst med musen
# (dobbeltklik = et ord, trippelklik = en linje eller et afsnit).
laes_ved_markering = {b(self.read_on_select)}
# Læs under musen med genveje: ordet, sætningen eller herfra og videre
# (se [genveje]). Virker i programmer med tilgængelighed, fx Firefox og LibreOffice.
laes_under_musen = {b(self.read_at_pointer)}

[diktering]
aktiv = {b(self.dictation_enabled)}
# Talegenkendelse (hentes automatisk første gang):
#   "dansk-hurtig" – dansk, hurtig (standard)      "dansk-turbo" – dansk, mere præcis, langsommere
#   "dansk-stor"   – dansk (CoRal røst), langsom   "hurtig"/"turbo" – generelle modeller
model = {s(self.dictation_model)}

[ordforslag]
# Forslag mens der skrives (på Linux kræver det IBus – se README)
aktiv = {b(self.prediction_enabled)}

[visning]
# Hvor knapperne vises: "knaplinje" (en lille linje på skærmen, standard)
# eller "ikoner" (et ikon for hver funktion ved uret)
knapper = {s(self.view)}

[ikoner]
# Hvilke knapper der vises ud over læs op, i knaplinjen eller som ikoner ved uret
# (dikter = mikrofon, skaerm = læs fra skærmen, pdf = gør en scannet PDF søgbar: teksten
# bliver til rigtig tekst, så den kan markeres og læses op. Står også i menuen).
{icons}

[genveje]
# Ønskede tastaturgenveje. På KDE kan de ændres i systemindstillingerne.
{hotkeys}
"""


def config_path() -> Path:
    return config_dir() / "config.toml"


# Til fluebenene, der lytter til tastaturet. Ordforslag og læs mens du skriver ser
# alle tastetryk i alle programmer (IBus på Linux, en tastaturovervågning på Windows).
KEYBOARD_PRIVACY_NOTE = (
    "Lytter til tastaturet i alle programmer for at se, hvad der skrives.\n"
    "Intet sendes nogen steder hen. Kun ord, du bruger, huskes på computeren."
)


def default_config(store_app: bool | None = None) -> Config:
    """Indstillingerne første gang.

    Fra Microsoft Store er ordforslag slået fra, til eleven selv slår det til: det lytter
    til alle tastetryk, og det skal være et bevidst valg (se packaging/windows/store/).
    """
    if store_app is None:
        from ordhjaelp.platform import is_store_app

        store_app = is_store_app()
    return Config(prediction_enabled=not store_app)


def load_config() -> Config:
    """Indlæs indstillinger. Første gang skrives en standardfil."""
    path = config_path()
    if not path.exists():
        save_config(default_config())
    return Config.from_toml(path.read_text(encoding="utf-8"))


def save_config(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(cfg.to_toml(), encoding="utf-8")
    tmp.replace(path)  # atomisk: aldrig en halvt skrevet fil
