import sys

import pytest

if sys.platform != "linux":  # Linux-kode (KWin over D-Bus). dbus-fast findes kun på Linux
    pytest.skip("kun Linux", allow_module_level=True)

from ordhjaelp.platform.linux.kwin_place import make_script  # noqa: E402


def test_script_finds_our_window_places_it_and_keeps_it_on_top() -> None:
    script = make_script(":1.42", 4711, 'Ordhjælp "x"', 24)
    assert "w.pid !== 4711" in script
    assert 'w.caption !== "Ordhj\\u00e6lp \\"x\\""' in script  # titlen er korrekt escapet
    assert "KWin.PlacementArea" in script  # skærmen minus opgavelinjen
    for prop in ("keepAbove", "skipTaskbar", "skipSwitcher", "skipPager", "onAllDesktops"):
        assert f"w.{prop} = true;" in script
    assert "a.x + a.width - g.width - 24" in script
    assert "a.y + a.height - g.height - 24" in script
    assert 'callDBus(":1.42", "/dk/ordhjaelp/KWin", "dk.ordhjaelp.KWin", "Report", ' in script
