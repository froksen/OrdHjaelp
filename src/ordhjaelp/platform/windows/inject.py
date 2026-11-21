"""Skriv dikteret tekst ind i det aktive program på Windows.

SendInput med KEYEVENTF_UNICODE skriver hvert tegn direkte, uafhængigt af
tastaturlayoutet. Så virker æ, ø, å, ?, ! og € ens på alle computere, og
udklipsholderen bliver ikke rørt.
"""

from __future__ import annotations

from ordhjaelp.platform.windows import win32


class WindowsKeyboard:
    def insert(self, text: str) -> None:
        if not text:
            return
        win32.wait_for_modifiers_released()
        win32.send_inputs(win32.unicode_inputs(text))
