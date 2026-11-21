"""Installér .desktop-fil (menu + evt. autostart) for den aktuelle bruger."""

from __future__ import annotations

import shlex
import shutil
import sys
from importlib.resources import files
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

from ordhjaelp.config import APP_ID

DESKTOP_NAME = f"{APP_ID}.desktop"


def _exec_command() -> str:
    exe = shutil.which("ordhjaelp")
    if exe:
        return shlex.quote(exe)
    return f"{shlex.quote(sys.executable)} -m ordhjaelp"


def render_desktop_file(exec_cmd: str) -> str:
    template = files("ordhjaelp.platform.linux").joinpath("data", DESKTOP_NAME).read_text("utf-8")
    return template.replace("@EXEC@", exec_cmd)


def install(autostart: bool) -> list[Path]:
    content = render_desktop_file(_exec_command())
    targets = [Path(user_data_dir("applications", appauthor=False, roaming=False)) / DESKTOP_NAME]
    if autostart:
        targets.append(Path(user_config_dir("autostart")) / DESKTOP_NAME)
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return targets


def uninstall() -> list[Path]:
    removed = []
    for target in (
        Path(user_data_dir("applications", appauthor=False, roaming=False)) / DESKTOP_NAME,
        Path(user_config_dir("autostart")) / DESKTOP_NAME,
    ):
        if target.exists():
            target.unlink()
            removed.append(target)
    return removed


def _autostart_path() -> Path:
    return Path(user_config_dir("autostart")) / DESKTOP_NAME


class LinuxAutostart:
    def is_enabled(self) -> bool:
        return _autostart_path().exists()

    def set_enabled(self, enabled: bool) -> None:
        path = _autostart_path()
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_desktop_file(_exec_command()), encoding="utf-8")
        elif path.exists():
            path.unlink()
