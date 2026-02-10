from __future__ import annotations

import sys
from pathlib import Path


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []

    # PyInstaller onefile temp extraction dir
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass))

    # Directory containing the executable (frozen) or script (dev)
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent)
    else:
        dirs.append(Path(__file__).resolve().parent)

    return dirs


def find_bundled_ffmpeg_dir() -> Path | None:
    """
    Returns a directory path suitable for yt-dlp's `ffmpeg_location`, if bundled ffmpeg is found.
    Expected layout:
      <base>/ffmpeg/ffmpeg.exe
      <base>/ffmpeg/ffprobe.exe
    """
    for base in _candidate_dirs():
        ffdir = base / "ffmpeg"
        ffmpeg = ffdir / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
        ffprobe = ffdir / ("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe")
        if ffmpeg.exists() and ffprobe.exists():
            return ffdir
    return None
