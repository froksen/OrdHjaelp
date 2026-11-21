"""Fanger lokalt på Linux det, der ellers først ville fejle på Windows.

Alt uden for platform/linux skal kunne importeres uden Linux-pakker (dbus-fast)
og uden at kalde Windows-DLL'er. Testen kører i en ny proces, hvor dbus_fast er
blokeret, ligesom på Windows.
"""

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "ordhjaelp"

SCRIPT = """
import importlib, sys
sys.modules["dbus_fast"] = None  # som på Windows: pakken findes ikke
for name in sys.argv[1:]:
    importlib.import_module(name)
print("ok")
"""


def _modules() -> list[str]:
    names = []
    for path in sorted(SRC.rglob("*.py")):
        parts = path.relative_to(SRC.parent).with_suffix("").parts
        if "linux" in parts or parts[-1] == "__main__":
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names.append(".".join(parts))
    return names


def test_everything_outside_linux_imports_without_dbus() -> None:
    modules = _modules()
    assert "ordhjaelp.platform.windows.selection" in modules
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT, *modules], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr


TESTS = Path(__file__).resolve().parent

TEST_SCRIPT = """
import importlib.util, sys
sys.modules["dbus_fast"] = None  # som på Windows
bad = []
for path in sys.argv[1:]:
    spec = importlib.util.spec_from_file_location("t", path)
    try:
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    except ImportError:
        source = open(path, encoding="utf-8").read()
        # Linux-tests må gerne kræve dbus-fast, hvis de springer sig selv over uden for Linux
        if not ("allow_module_level=True" in source and "sys.platform" in source):
            bad.append(path)
if bad:
    sys.exit("Testfiler, der fejler på Windows (mangler platform-skip): " + ", ".join(bad))
print("ok")
"""


def test_test_files_import_on_windows() -> None:
    files = [str(p) for p in sorted(TESTS.glob("test_*.py"))]
    files += [str(p) for p in sorted((TESTS / "ordmotor").glob("test_*.py"))]
    result = subprocess.run(
        [sys.executable, "-c", TEST_SCRIPT, *files],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=TESTS,
    )
    assert result.returncode == 0, result.stderr
