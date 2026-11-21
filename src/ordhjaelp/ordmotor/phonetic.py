"""Dansk lydnøgle: ord, der lyder ens, får samme nøgle.

Reglerne dækker typiske fejl hos ordblinde og yngre elever:
stumme bogstaver (hvad, hjem, mand, dejlig), b/p-d/t-g/k efter s (sgole),
dobbeltkonsonanter, c/k/s, æ/e, å/o og endelser som -er/-re/-a.

Nøglen bruges kun til at *finde* kandidater – rækkefølgen afgøres bagefter af
hyppighed og hvor tæt stavningen er på.
"""

from __future__ import annotations

import re

# Rækkefølgen betyder noget: længere mønstre før kortere.
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), r)
    for p, r in [
        # Fremmedord og særlige bogstaver
        (r"tion", "sjon"),
        (r"sch|sh|ch", "sj"),
        (r"ph", "f"),
        (r"ck", "k"),
        (r"c(?=[eiyæø])", "s"),
        (r"c", "k"),
        (r"q", "k"),
        (r"x", "ks"),
        (r"z", "s"),
        (r"w", "v"),
        (r"é", "e"),
        (r"aa", "å"),
        # Stumme bogstaver i starten: hvad, hvor, hjem, hjælpe
        (r"^hv", "v"),
        (r"^hj", "j"),
        # b/p, d/t, g/k efter s udtales ens: sgole = skole, sbille = spille
        (r"sb", "sp"),
        (r"sd", "st"),
        (r"sg", "sk"),
        # Stumt d: mand, hold, bord, fødselsdag, bedstemor, mindst, spændende
        (r"(?<=[lnr])d(?=[^aeiouyæøå]|$)", ""),
        (r"(?<=[lnr])d(?=e)", ""),
        (r"ds", "s"),
        (r"dst", "st"),
        # Stumt g: dejlig, pludselig, selvfølgelig, sjov/sjo
        (r"ig(?=e?$|t$|s$)", "i"),
        (r"lgel", "lel"),
        (r"(?<=[aeiouyæøå])g(?=e)", ""),
        # g efter a/o/å i slutningen: dag → da, bog → bo
        (r"(?<=[aoå])g$", ""),
        # r efter vokal før konsonant udtales næsten ikke: lørdag → lødag, tirsdag
        (r"(?<=[aeiouyæøå])r(?=[^aeiouyæøå])", ""),
        # v efter vokal i slutningen: sjov → sjo, selv → sel
        (r"(?<=[aeiouyæøå])v$", ""),
        (r"(?<=l)v(?=f)", ""),
        # Vokaler, der ofte forveksles
        (r"æ", "e"),
        (r"å", "o"),
        (r"ej|aj|eg(?=[^aeiouyæøå]|$)", "aj"),
        # Endelser: sover/sova, lærer/læra, større/størra
        (r"(er|re|ar|or)$", "a"),
        (r"(?<=[^aeiouyæøå])e$", "e"),
        # Dobbeltkonsonanter → én
        (r"([bdfgjklmnprstv])\1+", r"\1"),
    ]
]
_NON_LETTERS = re.compile(r"[^a-zæøåé]")


def danish_key(word: str) -> str:
    """Lydnøgle for et (helt eller delvist) dansk ord."""
    key = _NON_LETTERS.sub("", word.lower())
    for pattern, replacement in _RULES:
        key = pattern.sub(replacement, key)
    return key
