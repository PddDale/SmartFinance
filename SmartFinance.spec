# PyInstaller build definition for the Windows distribution.
from pathlib import Path


ROOT = Path(SPECPATH).resolve()
RESOURCE_ROOT = ROOT / "Recursos" / "Interface"

a = Analysis(
    [str(ROOT / "Recursos" / "Codigo" / "app.py")],
    pathex=[str(ROOT / "Recursos" / "Codigo")],
    binaries=[],
    datas=[
        (str(RESOURCE_ROOT / "templates"), "Recursos/Interface/templates"),
        (str(RESOURCE_ROOT / "static"), "Recursos/Interface/static"),
    ],
    hiddenimports=["waitress", "tkinter", "tkinter.filedialog"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartFinance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SmartFinance",
)
