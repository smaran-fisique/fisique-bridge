# -*- mode: python ; coding: utf-8 -*-
import sys

block_cipher = None

a = Analysis(
    ["bridge/main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("bridge/*.py", "bridge"),
        ("bridge/icon.png", "bridge"),
        ("bridge/icon.ico", "bridge"),
    ],
    hiddenimports=[
        "bridge",
        "bridge.app",
        "bridge.tray",
        "bridge.ui",
        "bridge.api",
        "bridge.config",
        "bridge.device",
        "bridge.server",
        "bridge.service",
        "bridge.sync",
        "bridge.cli",
        "bridge.main",
        "pystray._win32",
        "pystray._darwin",
        "pystray._xorg",
        "PIL._tkinter_finder",
        "zk",
        "zk.base",
        "zk.exception",
        "schedule",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FisiqueBridge",
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="bridge/icon.ico",
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="FisiqueBridge.app",
        icon="bridge/icon.ico",
        bundle_identifier="com.fisique.bridge",
        info_plist={
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.1.0",
        },
    )
