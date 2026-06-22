# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DSI Redline (one-folder, windowed).

Build from the repo root:
    pyinstaller packaging/DSI_Redline.spec --noconfirm
Produces dist/DSI Redline/  (run "DSI Redline.exe").
"""

import os

ROOT = os.path.dirname(os.path.abspath(SPECPATH))  # repo root (packaging/..)

# Bundle the user-manual vault and app assets (icon) so they ship with every build.
datas = [
    (os.path.join(ROOT, "docs"), "docs"),
    (os.path.join(ROOT, "app", "assets"), os.path.join("app", "assets")),
]

# Optionally bundle the Anthropic SDK (AI assist) only when it's installed,
# so builds without it still succeed and the app degrades gracefully.
hiddenimports = []
try:
    import anthropic  # noqa: F401
    from PyInstaller.utils.hooks import collect_submodules
    hiddenimports += collect_submodules("anthropic")
except Exception:
    pass

icon_path = os.path.join(ROOT, "app", "assets", "app.ico")  # brand icon

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DSI Redline",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # GUI app, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon_path if os.path.exists(icon_path) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DSI Redline",
)
