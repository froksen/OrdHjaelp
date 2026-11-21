"""Flyt et af Ordhjælps vinduer ned i hjørnet over opgavelinjen på KDE Plasma (Wayland).

På Wayland vælger skrivebordet selv, hvor et nyt vindue lægges, og programmet må
ikke flytte det. KWin må godt, så vi beder den om det med et lille script.
Vinduet findes ud fra vores proces-id og vinduestitlen.

KWins "PlacementArea" er skærmen minus paneler (opgavelinjen), så vinduet lægges
lige over opgavelinjen, uanset hvor den sidder.
"""

import json
import logging
import os

from ordhjaelp.platform.linux import kwin_script

log = logging.getLogger(__name__)

SCRIPT = """\
(function () {
  var moved = 0;
  var wins = workspace.stackingOrder;
  for (var i = 0; i < wins.length; i++) {
    var w = wins[i];
    try {
      if (w.pid !== %(pid)d || w.caption !== %(caption)s) continue;
      var a = workspace.clientArea(KWin.PlacementArea, w);
      var g = w.frameGeometry;
      w.frameGeometry = {
        x: a.x + a.width - g.width - %(margin)d,
        y: a.y + a.height - g.height - %(margin)d,
        width: g.width, height: g.height
      };
      moved++;
    } catch (e) {}
  }
  %(report)sString(moved));
})();
"""


def make_script(service: str, pid: int, caption: str, margin: int) -> str:
    return SCRIPT % {
        "pid": pid,
        "caption": json.dumps(caption),
        "margin": margin,
        "report": kwin_script.report_call(service),
    }


async def move_to_corner(caption: str, margin: int) -> bool:
    """Flyt vinduet nederst til højre. True, hvis KWin fandt og flyttede det."""
    if not await kwin_script.available():
        return False
    pid = os.getpid()
    answer = await kwin_script.run_script(
        lambda service: make_script(service, pid, caption, margin), "placer"
    )
    return answer.strip() not in ("", "0")
