# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

spec_dir = Path(globals().get("SPECPATH", os.getcwd())).resolve()
project_root = spec_dir.parent

ffmpeg_dir = project_root / "third_party" / "ffmpeg" / "windows"
assets_dir = project_root / "ytbatch" / "assets"

datas = []

# Bundle ffmpeg tools into "ffmpeg/"
if ffmpeg_dir.exists():
    datas.append((str(ffmpeg_dir / "ffmpeg.exe"), "ffmpeg"))
    datas.append((str(ffmpeg_dir / "ffprobe.exe"), "ffmpeg"))

# Bundle assets folder into "assets/" (required for resource_path(...))
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

a = Analysis(
    [str(project_root / "run_gui.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ytbatch-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(assets_dir / "icon.ico") if assets_dir.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="ytbatch-gui",
)
