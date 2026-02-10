# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

spec_dir = Path(globals().get("SPECPATH", os.getcwd())).resolve()
project_root = spec_dir.parent
ffmpeg_dir = project_root / "third_party" / "ffmpeg" / "windows"

datas = []
if ffmpeg_dir.exists():
    datas.append((str(ffmpeg_dir / "ffmpeg.exe"), "ffmpeg"))
    datas.append((str(ffmpeg_dir / "ffprobe.exe"), "ffmpeg"))

a = Analysis(
    [str(project_root / "run_cli.py")],
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
    name="ytbatch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="ytbatch",
)

