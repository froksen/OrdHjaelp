"""Indgangen til Ordhjaelp.exe (Windows-installeren).

Uden argumenter (fx fra genvejen i startmenuen) startes Ordhjælp. Med argumenter
virker den som kommandoen `ordhjaelp`, fx `Ordhjaelp.exe laes`.
"""

import os
import sys

# Programmet har ingen konsol, så print() må ikke fejle
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

from ordhjaelp.cli import main  # noqa: E402

sys.exit(main(sys.argv[1:] or ["start"]))
