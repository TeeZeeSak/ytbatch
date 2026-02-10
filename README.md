# ytbatch

Batch-search YouTube queries into a per-run CSV, then download audio/video using `yt-dlp`.

## Features
- Reads queries from file or manual input
- Always builds `output.csv` into a per-run folder (cache by default)
- Can skip searching and download directly from an existing `output.csv`
- Download modes:
  - `audio-mp3` (requires ffmpeg)
  - `audio-original` (keeps original audio container)
  - `video-original` (best video+audio, often requires ffmpeg for merge)
- CLI + GUI (PySide6)

## Install
### CLI only
```bash
pip install -e .
GUI
pip install -e ".[gui]"
CLI usage
Build CSV from list and download MP3
ytbatch --queries-file list.txt --mode audio-mp3 --out-dir downloads
Download only from existing CSV
ytbatch --from-csv path/to/output.csv --mode audio-mp3 --out-dir downloads
Manual queries (repeatable)
ytbatch --query "VAŠO PATEJDL - Ak nie si moja" --query "Další dotaz" --mode audio-original --out-dir downloads
Choose where run folders (CSV) go
ytbatch --queries-file list.txt --run-dir ./runs --mode audio-mp3 --out-dir downloads
GUI usage
ytbatch-gui
Paste queries or load a list file

Choose output folder and run folder (optional)

Build CSV

Start download

Notes
MP3 extraction requires ffmpeg in PATH.

Respect content owners and platform terms.


---

# 5) `ytbatch/__init__.py`

```python
__all__ = ["core", "models", "storage"]
__version__ = "0.1.0"