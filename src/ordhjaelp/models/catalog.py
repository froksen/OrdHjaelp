"""Katalog over de sprogmodeller, Ordhjælp kan hente.

Alle modeller er færdige og vedligeholdes af andre – Ordhjælp henter dem bare.
Nye modeller (fx flere stemmer) tilføjes ved at skrive dem ind her.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Kind(enum.Enum):
    VOICE = "stemme"  # oplæsning (Piper)
    SPEECH = "tale"  # talegenkendelse/diktering (faster-whisper)


@dataclass(frozen=True)
class ModelInfo:
    id: str  # stemmenavn (Piper) eller kaldenavn i indstillingerne (Whisper)
    kind: Kind
    title: str
    description: str
    size_mb: int
    source: str  # Piper-stemmenavn eller Hugging Face-repo/faster-whisper-navn
    recommended: bool = False


CATALOG: list[ModelInfo] = [
    ModelInfo(
        "da_DK-talesyntese-medium",
        Kind.VOICE,
        "Dansk stemme",
        "Læser tekst op med en naturlig dansk stemme.",
        63,
        "da_DK-talesyntese-medium",
        recommended=True,
    ),
    ModelInfo(
        "dansk-hurtig",
        Kind.SPEECH,
        "Dansk – hurtig",
        "Hurtig dansk talegenkendelse. Passer til de fleste computere.",
        249,
        "lucasw89/whisper-small-danish-ct2-int8",
        recommended=True,
    ),
    ModelInfo(
        "dansk-turbo",
        Kind.SPEECH,
        "Dansk – præcis",
        "Mere præcis, men langsommere. Kræver en hurtig computer.",
        1621,
        "q-henric/whisper-large-v3-turbo-danish-ct2",
    ),
    ModelInfo(
        "dansk-stor",
        Kind.SPEECH,
        "Dansk – CoRal røst",
        "Trænet på mange danske dialekter, men langsom og uden tegnsætning.",
        3092,
        "pluttodk/roest-v3-whisper-1.5b-ct2",
    ),
    ModelInfo(
        "hurtig",
        Kind.SPEECH,
        "Flersproget – hurtig",
        "Generel model (også engelsk), svagere på dansk.",
        486,
        "small",
    ),
    ModelInfo(
        "turbo",
        Kind.SPEECH,
        "Flersproget – præcis",
        "Generel model (også engelsk), langsommere.",
        1621,
        "large-v3-turbo",
    ),
]

_BY_ID = {m.id: m for m in CATALOG}


def get(model_id: str) -> ModelInfo | None:
    return _BY_ID.get(model_id)


def of_kind(kind: Kind) -> list[ModelInfo]:
    return [m for m in CATALOG if m.kind is kind]


def size_text(size_mb: int) -> str:
    if size_mb >= 1000:
        return f"{size_mb / 1000:.1f} GB".replace(".", ",")
    return f"{size_mb} MB"
