# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


block_cipher = None

datas = []
hiddenimports = [
    "PIL._tkinter_finder",
    "tkinterdnd2",
]

try:
    datas += collect_data_files("tkinterdnd2")
except Exception:
    pass

try:
    datas += collect_data_files("rembg")
except Exception:
    pass

for dist_name in (
    "rembg",
    "PyMatting",
    "onnxruntime",
    "numba",
    "llvmlite",
    "scipy",
    "scikit-image",
    "pooch",
    "jsonschema",
    "numpy",
    "Pillow",
):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

u2net_model = os.path.expanduser("~/.u2net/u2net.onnx")
if os.path.exists(u2net_model):
    datas.append((u2net_model, "u2net"))
else:
    print(f"WARNING: u2net model not found at {u2net_model}; rembg may download it on first use.")

for package_name in ("rembg", "pymatting", "onnxruntime"):
    try:
        hiddenimports += collect_submodules(package_name)
    except Exception:
        pass


a = Analysis(
    ["SpriteAnchor.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyinstaller_hooks/rembg_runtime.py"],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpriteAnchor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SpriteAnchor",
)

app = BUNDLE(
    coll,
    name="SpriteAnchor.app",
    icon=None,
    bundle_identifier="com.spriteanchor.app",
    info_plist={
        "CFBundleName": "SpriteAnchor",
        "CFBundleDisplayName": "SpriteAnchor",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "10.13",
    },
)
