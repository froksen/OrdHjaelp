"""Musens position og vinduet under den på KDE Plasma (Wayland) via et lille KWin-script.

På Wayland må almindelige programmer ikke se, hvor musen er. KWin (KDE's
vindueshåndtering) ved det, og den kan køre små JavaScript-filer. Scriptet
sender svaret tilbage til os over D-Bus (se kwin_script.py).
"""

import json
import logging
from dataclasses import dataclass

from ordhjaelp.platform.linux import kwin_script
from ordhjaelp.platform.linux.kwin_script import available  # noqa: F401 - bruges af pointer.py

log = logging.getLogger(__name__)

# Gennemgår vinduerne oppefra og finder det øverste, som musen står over.
SCRIPT = """\
(function () {
  var pos = workspace.cursorPos;
  var found = {x: pos.x, y: pos.y, pid: 0, caption: "", clientX: 0, clientY: 0};
  var wins = workspace.stackingOrder;
  for (var i = wins.length - 1; i >= 0; i--) {
    var w = wins[i];
    try {
      if (w.minimized || w.deleted) continue;
      if (!w.onAllDesktops && w.desktops && w.desktops.indexOf(workspace.currentDesktop) < 0)
        continue;
      var g = w.frameGeometry;
      if (pos.x < g.x || pos.y < g.y || pos.x >= g.x + g.width || pos.y >= g.y + g.height)
        continue;
      var c = w.clientGeometry;
      found.pid = w.pid; found.caption = w.caption; found.clientX = c.x; found.clientY = c.y;
      break;
    } catch (e) {}
  }
  %(report)sJSON.stringify(found));
})();
"""


@dataclass(frozen=True)
class PointerInfo:
    x: int
    y: int
    pid: int = 0
    caption: str = ""
    client_x: int = 0
    client_y: int = 0

    @property
    def window_x(self) -> int:
        return self.x - self.client_x

    @property
    def window_y(self) -> int:
        return self.y - self.client_y


def make_script(service: str) -> str:
    return SCRIPT % {"report": kwin_script.report_call(service)}


def parse_report(data: str) -> PointerInfo:
    raw = json.loads(data)
    return PointerInfo(
        x=round(float(raw.get("x", 0))),
        y=round(float(raw.get("y", 0))),
        pid=int(raw.get("pid") or 0),
        caption=str(raw.get("caption") or ""),
        client_x=round(float(raw.get("clientX", 0))),
        client_y=round(float(raw.get("clientY", 0))),
    )


async def locate() -> PointerInfo:
    """Spørg KWin, hvor musen er, og hvilket vindue den står over."""
    return parse_report(await kwin_script.run_script(make_script, "mus"))
