from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """
    Resolve resource paths both in dev and PyInstaller frozen mode.
    Expects assets to be included under: ytbatch/assets/...
    In PyInstaller, we bundle them into an "assets" folder.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).resolve() / "assets" / Path(*parts)
    return Path(__file__).resolve().parent / "assets" / Path(*parts)
