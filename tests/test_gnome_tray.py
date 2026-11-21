"""Ikoner ved uret på GNOME: find udvidelsen, slå den til og vent på den."""

import subprocess
import sys

import pytest

if sys.platform != "linux":
    pytest.skip("kun Linux", allow_module_level=True)

from ordhjaelp.platform.linux import gnome  # noqa: E402

UUID = gnome.UUIDS[0]


class FakeShell:
    """Svarer som gnome-extensions og gdbus."""

    def __init__(self, installed=(), enabled=(), watcher=False) -> None:  # noqa: ANN001
        self.installed = set(installed)
        self.enabled = set(enabled)
        self.watcher = watcher
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        out, code = "", 0
        if cmd[:2] == ["gnome-extensions", "list"]:
            out = "\n".join(self.enabled if "--enabled" in cmd else self.installed)
        elif cmd[:2] == ["gnome-extensions", "enable"]:
            if cmd[2] in self.installed:
                self.enabled.add(cmd[2])
                self.watcher = True
            else:
                code = 2
        elif cmd[0] == "gdbus":
            out = "(true,)" if self.watcher else "(false,)"
        return subprocess.CompletedProcess(cmd, code, out, "")


@pytest.fixture
def shell(monkeypatch):
    fake = FakeShell()
    monkeypatch.setattr(gnome, "_run", fake)
    return fake


@pytest.mark.parametrize(
    ("desktop", "expected"),
    [("GNOME", True), ("ubuntu:GNOME", True), ("KDE", False), ("", False)],
)
def test_is_gnome(monkeypatch, desktop: str, expected: bool) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
    assert gnome.is_gnome() is expected


def test_missing(shell) -> None:
    assert gnome.AppIndicatorExtension().state() == gnome.MISSING
    assert not gnome.AppIndicatorExtension().enable()


def test_installed_but_disabled_can_be_enabled(shell) -> None:
    shell.installed = {UUID, "andet@eksempel"}
    ext = gnome.AppIndicatorExtension()
    assert ext.state() == gnome.DISABLED
    assert not ext.wait_until_ready(0)
    assert ext.enable()
    assert ["gnome-extensions", "enable", UUID] in shell.calls
    assert ext.state() == gnome.ENABLED
    assert ext.wait_until_ready(0)


def test_ubuntu_variant_is_recognised(shell) -> None:
    shell.installed = shell.enabled = {"ubuntu-appindicators@ubuntu.com"}
    assert gnome.AppIndicatorExtension().state() == gnome.ENABLED


def test_install_command_names_the_package() -> None:
    assert gnome.PACKAGE in gnome.AppIndicatorExtension().install_command


def test_only_gnome_gets_an_extension(monkeypatch) -> None:
    from ordhjaelp.platform import get_tray_extension

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert get_tray_extension() is None
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert isinstance(get_tray_extension(), gnome.AppIndicatorExtension)
