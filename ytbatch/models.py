from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DownloadMode(str, Enum):
    AUDIO_MP3 = "audio-mp3"
    AUDIO_ORIGINAL = "audio-original"
    VIDEO_ORIGINAL = "video-original"


@dataclass(frozen=True)
class SearchRow:
    query: str
    video_url: str
    video_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    csv_path: Path
