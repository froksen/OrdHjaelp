"""Ordliste med hyppigheder – bygget af færdige, vedligeholdte kilder.

* Hyppigheder: wordfreq (dansk).
* Filter og store bogstaver: den danske Hunspell-ordbog (Stavekontrolden.dk),
  så engelske ord, tal og stavefejl fra internettet ikke bliver foreslået.

Listen bygges én gang og gemmes som JSON.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

LEXICON_VERSION = 1
MAX_WORDS = 100_000
_WORD = re.compile(r"[a-zæøåéü]+(?:-[a-zæøåéü]+)?")


@dataclass(frozen=True)
class Entry:
    word: str  # sådan ordet skal skrives (fx "København")
    zipf: float  # hyppighed, 1 (sjælden) – 7 (meget hyppig)


def _hunspell_accepts(words: list[str]) -> set[str] | None:
    """Ord, som den danske Hunspell-ordbog godkender (None hvis Hunspell mangler)."""
    if shutil.which("hunspell") is None:
        return None
    try:
        result = subprocess.run(
            ["hunspell", "-d", "da_DK", "-G", "-i", "utf-8"],
            input="\n".join(words).encode(),
            capture_output=True,
            timeout=120,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # intet konsolvindue
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return set(result.stdout.decode("utf-8").split())


def build_entries() -> list[Entry]:
    from wordfreq import top_n_list, zipf_frequency

    words = [
        w
        for w in top_n_list("da", MAX_WORDS)
        if _WORD.fullmatch(w) and len(w) > 1 or w in ("i", "å", "ø")
    ]
    # Engelske ord fra sociale medier: meget hyppigere på engelsk end på dansk
    words = [
        w
        for w in words
        if not (
            zipf_frequency(w, "en") > 5.0
            and zipf_frequency(w, "en") - zipf_frequency(w, "da") > 1.0
        )
    ]
    capitalized = [w[:1].upper() + w[1:] for w in words]
    accepted = _hunspell_accepts(words + capitalized)
    if accepted is None:
        log.warning("Hunspell (da_DK) ikke fundet – ordlisten bliver ikke filtreret")

    entries: list[Entry] = []
    for word, cap in zip(words, capitalized, strict=True):
        if accepted is None or word in accepted:
            entries.append(Entry(word, zipf_frequency(word, "da")))
        elif cap in accepted:  # findes kun med stort: navne og stednavne
            entries.append(Entry(cap, zipf_frequency(word, "da")))
    return entries


def load_entries(cache: Path) -> list[Entry]:
    try:
        raw = json.loads(cache.read_text(encoding="utf-8"))
        if raw.get("version") == LEXICON_VERSION:
            return [Entry(w, z) for w, z in raw["words"]]
    except (OSError, ValueError, KeyError):
        pass
    log.info("Bygger ordliste …")
    entries = build_entries()
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {"version": LEXICON_VERSION, "words": [[e.word, round(e.zipf, 2)] for e in entries]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    tmp.replace(cache)
    log.info("Ordliste klar: %d ord", len(entries))
    return entries
