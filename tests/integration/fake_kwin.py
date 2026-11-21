"""Falsk KWin-scripting til test_atspi.py (uden __future__-annotationer, se kwin_pointer.py)."""

from pathlib import Path

from dbus_fast.service import ServiceInterface, method


class Scripting(ServiceInterface):
    def __init__(self, owner) -> None:  # noqa: ANN001
        super().__init__("org.kde.kwin.Scripting")
        self._owner = owner
        self._scripts: dict[int, str] = {}

    @method()
    def loadScript(self, path: "s", plugin: "s") -> "i":  # noqa: F821, N802
        script_id = len(self._scripts) + 1
        self._scripts[script_id] = Path(path).read_text(encoding="utf-8")
        # KWin laver et objekt pr. script. Her svarer vi bare på run() med det samme.
        self._owner._bus.export(
            f"/Scripting/Script{script_id}", _Script(self._owner, self._scripts[script_id])
        )
        return script_id

    @method()
    def unloadScript(self, plugin: "s") -> "b":  # noqa: F821, N802
        self._owner.unloaded.append(plugin)
        return True


class _Script(ServiceInterface):
    def __init__(self, owner, script: str) -> None:  # noqa: ANN001
        super().__init__("org.kde.kwin.Script")
        self._owner = owner
        self._script = script

    @method()
    def run(self):  # noqa: ANN201
        self._owner.script_run(self._script)
