from __future__ import annotations

from datetime import datetime
from pathlib import Path

from platformdirs import user_cache_dir

APP_NAME = "ytbatch"


def default_base_run_dir() -> Path:
    # Per-user cache dir (not Desktop)
    return Path(user_cache_dir(APP_NAME))


def make_run_dir(base_dir: Path | None = None) -> Path:
    base = base_dir or default_base_run_dir()
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = base / "runs" / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
