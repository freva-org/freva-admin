# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import sys

# ---------------------------------------------------
# Clean old build and dist folders (equivalent to --clean)
# ---------------------------------------------------
project_dir = Path.cwd().parent.resolve()
for folder in ["build", "dist"]:
    target = project_dir / folder
    if target.exists() and target.is_dir():
        print(f"Cleaning existing folder: {target}")
        shutil.rmtree(target)


# ---------------------------------------------------
# Optional: clean old spec files (only if generated)
# ---------------------------------------------------
# spec_file = project_dir / "deploy-freva.spec"
# if spec_file.exists():
#     print(f"Removing old spec file: {spec_file}")
#     spec_file.unlink()

# ---------------------------------------------------
# Setup binaries
# ---------------------------------------------------
bins = []
for bin in ("mysqldump",):
    exe = shutil.which(bin)
    if exe:
        bins.append((exe, "bin"))

# ---------------------------------------------------
# Hidden imports
# ---------------------------------------------------
hiddenimports = ["tomlkit", "cryptography", "ansible_pylibssh", "ansible"]

# ---------------------------------------------------
# Data files
# ---------------------------------------------------
data = [
    ("assets/share/freva/deployment", "freva_deployment/assets"),
    ("src/freva_deployment/versions.json", "freva_deployment"),
    ("src/freva_deployment/callback_plugins", "freva_deployment/callback_plugins"),
]
binaries = bins

# ---------------------------------------------------
# Collect all from ansible & ansible_collections
# ---------------------------------------------------
for package in ("ansible", "ansible_collections"):
    all_data = collect_all(package)
    data += all_data[0]
    binaries += all_data[1]
    hiddenimports += all_data[2]

# ---------------------------------------------------
# ✅ Filter out accidental _internal folders
# ---------------------------------------------------
data = [d for d in data if "_internal" not in d[0] and "_internal" not in d[1]]
binaries = [b for b in binaries if "_internal" not in b[0] and "_internal" not in b[1]]
# ---------------------------------------------------
# PyInstaller build
# ---------------------------------------------------
a = Analysis(
    ["pyinstaller/pyinstaller-deploy-freva.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    data=data,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pycrypto", "PyInstaller", "cowsay"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='deploy-freva',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
    icon=['docs/_static/freva_owl.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='deploy-freva',
)
