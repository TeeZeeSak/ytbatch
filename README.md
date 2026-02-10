# ytbatch

**ytbatch** is a desktop + CLI tool for batch-searching YouTube queries and downloading the first result as audio or video.

It builds a reproducible CSV run file, supports resuming downloads, bundles ffmpeg, and works fully offline after packaging.

---

## Features

* Batch search YouTube from:

  * `list.txt`
  * Manual input (GUI)
  * Dropped `.csv`
* Automatically builds a `output.csv` run file
* Download modes:

  * Audio (MP3)
  * Original video format
  * Best quality video
* Skip existing files
* Resume from CSV
* Drag & drop support
* Dark mode (System / Light / Dark)
* Bundled `ffmpeg` + `ffprobe`
* Windows EXE build via PyInstaller
* UTF-8 BOM-safe CSV handling

---

## Project Structure

```
ytbatch/
  cli.py
  core.py
  models.py
  storage.py
  resources.py
  gui/
    app.py
    worker.py
  assets/
    icon.png
    icon.ico

third_party/
  ffmpeg/windows/
    ffmpeg.exe
    ffprobe.exe

packaging/
  ytbatch-cli.spec
  ytbatch-gui.spec
```

---

## Installation (Development)

### 1. Clone

```bash
git clone https://github.com/yourname/ytbatch.git
cd ytbatch
```

### 2. Install (editable mode)

```bash
pip install -e .
pip install -e ".[gui]"
```

### 3. Run

CLI:

```bash
ytbatch
```

GUI:

```bash
ytbatch-gui
```

Or directly:

```bash
python run_gui.py
```

---

## CLI Usage

### Build CSV only

```bash
ytbatch --list list.txt --mode audio --no-download
```

### Download from existing CSV

```bash
ytbatch --from-csv runs/2024-01-01_12-00/output.csv --mode audio
```

### Keep original video format

```bash
ytbatch --list list.txt --mode original
```

---

## GUI Usage

* Paste queries (one per line) **or**
* Drop a `.txt` file **or**
* Drop a previously generated `output.csv`
* Choose mode
* Click **Start**

### Drag & Drop

Drop:

* `.txt` → populates query list
* `.csv` → loads previous run and downloads directly

---

## Build Windows EXE

Requires PyInstaller.

### GUI

```bash
pyinstaller --noconfirm --clean packaging/ytbatch-gui.spec
```

### CLI

```bash
pyinstaller --noconfirm --clean packaging/ytbatch-cli.spec
```

Output will be in:

```
dist/ytbatch-gui/
```

Do not move the EXE out of this folder if building in onedir mode.

---

## Requirements

* Python 3.10+
* yt-dlp
* PySide6 (GUI)
* ffmpeg (bundled in Windows build)

---

## How It Works

1. Each query is searched via `yt-dlp`.
2. First result URL + metadata are stored in `output.csv`.
3. Downloads are executed from CSV entries.
4. CSV acts as reproducible cache and resume point.

---

## Why CSV?

* Transparent
* Inspectable
* Re-runnable
* Versionable
* No hidden state

---

## License

MIT License

---

## Notes

* YouTube throttling is intentionally avoided (no parallel aggressive downloading).
* CSV parsing is UTF-8 BOM safe.
* Windows icon cache may require Explorer restart after rebuild.

---

## Status

Stable for personal use.
Modular structure allows extension to:

* Parallel downloads
* Playlist support
* Metadata tagging
* Automatic updates
* macOS / Linux builds

