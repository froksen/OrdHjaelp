"""Klargøring af tekst før oplæsning."""

from __future__ import annotations

import re

# "ord-\ndeling" fra PDF'er og ombrudt tekst -> "orddeling"
_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
_WHITESPACE = re.compile(r"\s+")


def normalize_for_speech(text: str) -> str:
    """Saml ombrudt tekst til flydende tekst, som stemmen kan læse naturligt."""
    text = text.replace("\r\n", "\n").replace("\u00ad", "")  # blød bindestreg

    def join(match: re.Match[str]) -> str:
        before, after = match.group(1), match.group(2)
        # Behold bindestregen ved store bogstaver/tal (EU-Lande, 2-3)
        if after.isupper() or after.isdigit() or before.isdigit():
            return f"{before}-{after}"
        return before + after

    text = _HYPHEN_BREAK.sub(join, text)
    return _WHITESPACE.sub(" ", text).strip()
