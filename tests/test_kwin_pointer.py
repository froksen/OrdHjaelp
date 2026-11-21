import sys

import pytest

if sys.platform != "linux":  # Linux-kode (KWin over D-Bus). dbus-fast findes kun på Linux
    pytest.skip("kun Linux", allow_module_level=True)

import json  # noqa: E402

from ordhjaelp.platform.linux.kwin_pointer import PointerInfo, make_script, parse_report


def test_script_reports_back_to_our_dbus_name() -> None:
    script = make_script(":1.42")
    assert 'callDBus(":1.42", "/dk/ordhjaelp/KWin", "dk.ordhjaelp.KWin", "Report"' in script
    assert "workspace.cursorPos" in script
    assert "workspace.stackingOrder" in script


def test_parse_report_rounds_fractional_positions() -> None:
    data = json.dumps(
        {"x": 120.6, "y": 40.2, "pid": 77, "caption": "Dok", "clientX": 100, "clientY": 30}
    )
    info = parse_report(data)
    assert info == PointerInfo(x=121, y=40, pid=77, caption="Dok", client_x=100, client_y=30)
    assert (info.window_x, info.window_y) == (21, 10)


def test_parse_report_without_window() -> None:
    info = parse_report(json.dumps({"x": 5, "y": 6, "pid": 0, "caption": ""}))
    assert info.pid == 0 and info.caption == ""


def test_pointer_commands_have_hotkeys_and_descriptions() -> None:
    from ordhjaelp.config import Config
    from ordhjaelp.daemon import POINTER_COMMANDS
    from ordhjaelp.platform.linux.hotkeys import DESCRIPTIONS

    assert set(POINTER_COMMANDS) == {"laes_ord", "laes_saetning", "laes_herfra"}
    for command in POINTER_COMMANDS:
        assert command in Config().hotkeys
        assert command in DESCRIPTIONS
