# PyInstaller: pak Ordhjælp og Python i én mappe (dist\Ordhjaelp\).
# Bruges af build-installer.ps1. Kør fra repoets rod:
#   uv run --group windows-build pyinstaller packaging\windows\ordhjaelp.spec
# -*- mode: python -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

HERE = Path(SPECPATH)  # noqa: F821 - sættes af PyInstaller
ROOT = HERE.parent.parent

# Ordhjælp importerer meget først, når det bruges. Tag alt med undtagen Linux-delen.
hiddenimports = collect_submodules(
    "ordhjaelp", filter=lambda name: not name.startswith("ordhjaelp.platform.linux")
)

datas = []
datas += collect_data_files("ordhjaelp", excludes=["platform/linux/**"])  # ikonerne
datas += collect_data_files("piper", includes=["espeak-ng-data/**"])  # udtale til stemmen
datas += collect_data_files("faster_whisper")  # silero VAD
# wordfreq har ordlister til mange sprog (ca. 58 MB). Ordhjælp bruger kun dansk og
# engelsk (engelsk til at sortere engelske ord fra sociale medier fra ordlisten).
datas += [
    (src, dest)
    for src, dest in collect_data_files("wordfreq")
    if Path(src).name.endswith(("_da.msgpack.gz", "_en.msgpack.gz"))
]

# huggingface_hub spørger efter hf_xet's versionsnummer, før det bruges til hurtig hentning
datas += copy_metadata("hf_xet")

binaries = []
binaries += collect_dynamic_libs("ctranslate2")  # talegenkendelse
# Søgbare PDF'er: pdfium.dll og versionsfilerne, som pypdfium2 læser ved import
binaries += collect_dynamic_libs("pypdfium2_raw")
datas += collect_data_files("pypdfium2_raw") + collect_data_files("pypdfium2")

a = Analysis(  # noqa: F821
    [str(HERE / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "dbus_fast", "gi", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ordhjaelp",
    icon=str(HERE / "build" / "ordhjaelp.ico"),
    console=False,  # intet sort konsolvindue
    version=str(HERE / "build" / "version.txt"),
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="Ordhjaelp",
)
