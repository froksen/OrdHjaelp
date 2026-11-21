"""Ordforslag: fuldfør ord og ret stavefejl – også fonetiske.

Tre veje til kandidater, som derefter rangeres samlet:
1. Begyndelsen passer:   "sko"    → skole, skoen, sko …
2. Lyden passer:         "sgole"  → skole,  "vordan" → hvordan
3. Stavningen er tæt på: "fotbol" → fodbold
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz.distance import Levenshtein

from ordhjaelp.ordmotor.lexicon import Entry
from ordhjaelp.ordmotor.phonetic import danish_key

MAX_SCAN = 4000  # højst så mange ord gennemgås pr. vej (holder det hurtigt)


@dataclass(frozen=True)
class Suggestion:
    word: str
    score: float
    exact_prefix: bool  # True hvis det, eleven har skrevet, er begyndelsen af ordet


class Predictor:
    def __init__(self, entries: Iterable[Entry], learned: dict[str, int] | None = None) -> None:
        self._learned: dict[str, int] = dict(learned or {})
        self._learned_low: dict[str, int] = {}
        for word, count in self._learned.items():
            self._learned_low[word.lower()] = self._learned_low.get(word.lower(), 0) + count
        self._zipf: dict[str, float] = {}
        self._display: dict[str, str] = {}
        for e in entries:
            low = e.word.lower()
            if low not in self._zipf or e.zipf > self._zipf[low]:
                self._zipf[low] = e.zipf
                self._display[low] = e.word
        for word in self._learned:
            self._add_word(word)
        self._rebuild_indexes()

    # -- offentlig API -------------------------------------------------
    def suggest(self, typed: str, n: int = 5) -> list[Suggestion]:
        typed_low = typed.lower()
        if not typed_low.isalpha() and "-" not in typed_low:
            return []
        scores: dict[str, tuple[float, bool]] = {}

        def consider(low: str, bonus: float, exact: bool) -> None:
            score = self._base(low) + bonus
            old = scores.get(low)
            if old is None or score > old[0]:
                scores[low] = (score, exact or (old[1] if old else False))

        # 1) begyndelsen passer (korte begyndelser: de hyppigste ord)
        if len(typed_low) <= 2:
            starts = [w for w in self._by_prefix2.get(typed_low[:2], ()) if w.startswith(typed_low)]
        else:
            starts = self._prefix_range(self._sorted, typed_low)
        for low in starts:
            consider(low, 2.0, True)

        if len(typed_low) >= 2:
            # 2) lyden passer
            key = danish_key(typed_low)
            if key:
                for low in self._key_prefix_range(key):
                    sim = Levenshtein.normalized_similarity(typed_low, low[: len(typed_low) + 1])
                    consider(low, 0.8 + sim, False)

        if len(typed_low) >= 3:
            # 3) stavningen er tæt på (samme første lyd)
            typed_key = danish_key(typed_low)
            first = typed_key[:1] or typed_low[:1]
            for low in self._by_first_sound.get(first, ()):
                whole = Levenshtein.normalized_similarity(typed_low, low)
                start = Levenshtein.normalized_similarity(typed_low, low[: len(typed_low)])
                sound = Levenshtein.normalized_similarity(typed_key, self._key_of[low])
                sim = max(whole, start * 0.95, sound * 0.95)
                if sim >= 0.7:
                    consider(low, 3.0 * sim - 1.5, False)

        ranked = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
        return [
            Suggestion(self._cased(low, typed), score, exact) for low, (score, exact) in ranked[:n]
        ]

    def learn(self, word: str) -> None:
        """Husk et ord, eleven har brugt – det bliver foreslået oftere."""
        low = word.lower()
        if not low or not (low.replace("-", "").isalpha()):
            return
        self._learned[word] = self._learned.get(word, 0) + 1
        self._learned_low[low] = self._learned_low.get(low, 0) + 1
        if low not in self._zipf and self._learned[word] >= 2:
            # Nyt ord (fx et navn), brugt mindst to gange → med i ordlisten
            self._add_word(word)
            self._rebuild_indexes()

    @property
    def learned(self) -> dict[str, int]:
        return dict(self._learned)

    def knows(self, word: str) -> bool:
        return word.lower() in self._zipf

    # -- intern ---------------------------------------------------------
    def _add_word(self, word: str) -> None:
        low = word.lower()
        if low not in self._zipf:
            self._zipf[low] = 2.0
            self._display[low] = word

    def _rebuild_indexes(self) -> None:
        self._sorted = sorted(self._zipf)
        self._key_of = {w: danish_key(w) for w in self._zipf}
        keyed = sorted((k, w) for w, k in self._key_of.items())
        self._keys = [k for k, _ in keyed]
        self._key_words = [w for _, w in keyed]
        by_first: dict[str, list[str]] = {}
        for word in sorted(self._zipf, key=self._zipf.get, reverse=True):
            first = self._key_of[word][:1] or word[:1]
            by_first.setdefault(first, []).append(word)
        self._by_first_sound = {k: v[:MAX_SCAN] for k, v in by_first.items()}
        by_prefix: dict[str, list[str]] = {}
        for word in sorted(self._zipf, key=self._zipf.get, reverse=True):
            for i in (1, 2):
                if len(word) >= i:
                    lst = by_prefix.setdefault(word[:i], [])
                    if len(lst) < 200:
                        lst.append(word)
        self._by_prefix2 = by_prefix

    def _base(self, low: str) -> float:
        return self._zipf.get(low, 2.0) + 1.5 * math.log1p(self._learned_low.get(low, 0))

    @staticmethod
    def _prefix_range(sorted_words: list[str], prefix: str) -> list[str]:
        lo = bisect.bisect_left(sorted_words, prefix)
        hi = bisect.bisect_left(sorted_words, prefix + "￿")
        return sorted_words[lo : min(hi, lo + MAX_SCAN)]

    def _key_prefix_range(self, key: str) -> list[str]:
        lo = bisect.bisect_left(self._keys, key)
        hi = bisect.bisect_left(self._keys, key + "￿")
        return self._key_words[lo : min(hi, lo + MAX_SCAN)]

    def _cased(self, low: str, typed: str) -> str:
        word = self._display.get(low, low)
        if typed[:1].isupper():
            return word[:1].upper() + word[1:]
        return word
