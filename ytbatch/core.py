from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Callable, Iterable

from yt_dlp import YoutubeDL

from .ffmpeg import find_bundled_ffmpeg_dir
from .models import DownloadMode, RunPaths, SearchRow
from .storage import make_run_dir

ProgressCallback = Callable[[dict], None]  # yt-dlp progress dict

_ID_IN_BRACKETS_RE = re.compile(r"\[([A-Za-z0-9_-]{6,})\]")


def normalize_query_lines(lines: Iterable[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        q = line.strip()
        if not q or q.startswith("#"):
            continue
        out.append(q)
    return out


def read_queries_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing queries file: {path}")
    return normalize_query_lines(path.read_text(encoding="utf-8-sig", errors="replace").splitlines())


def first_youtube_video(query: str, *, socket_timeout: int = 15, retries: int = 3) -> dict | None:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch",
        "socket_timeout": socket_timeout,
        "retries": retries,
    }
    search_term = f"ytsearch1:{query}"
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_term, download=False)
        entries = info.get("entries") or []
        return entries[0] if entries else None


def entry_to_row(query: str, entry: dict) -> SearchRow:
    video_id = (entry.get("id") or "").strip()
    title = (entry.get("title") or "").strip()
    url = (entry.get("url") or "").strip()

    if url and not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={video_id or url}"

    return SearchRow(query=query, video_url=url, video_id=video_id, title=title)


def build_run_csv(
    queries: list[str],
    *,
    base_run_dir: Path | None = None,
    csv_filename: str = "output.csv",
    on_status: Callable[[str], None] | None = None,
) -> tuple[RunPaths, list[SearchRow]]:
    run_dir = make_run_dir(base_run_dir)
    csv_path = run_dir / csv_filename

    rows: list[SearchRow] = []
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["query", "video_url", "video_id", "title"])

        for q in queries:
            if on_status:
                on_status(f"Searching: {q}")
            try:
                entry = first_youtube_video(q)
            except Exception as e:
                writer.writerow([q, "", "", f"ERROR: {e}"])
                if on_status:
                    on_status(f"  -> ERROR: {e}")
                continue

            if not entry:
                writer.writerow([q, "", "", "NO RESULTS"])
                if on_status:
                    on_status("  -> NO RESULTS")
                continue

            row = entry_to_row(q, entry)
            writer.writerow([row.query, row.video_url, row.video_id, row.title])
            rows.append(row)
            if on_status:
                on_status(f"  -> {row.title} [{row.video_id}]")

    return RunPaths(run_dir=run_dir, csv_path=csv_path), rows


def load_rows_from_csv(csv_path: Path) -> list[SearchRow]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV file: {csv_path}")

    rows: list[SearchRow] = []
    with csv_path.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        required = {"query", "video_url"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"{csv_path} missing columns {sorted(required)}; found: {reader.fieldnames}")

        for r in reader:
            q = (r.get("query") or "").strip()
            url = (r.get("video_url") or "").strip()
            vid = (r.get("video_id") or "").strip()
            title = (r.get("title") or "").strip()

            if not url or url.upper().startswith("ERROR") or url.upper().startswith("NO RESULTS"):
                continue
            rows.append(SearchRow(query=q, video_url=url, video_id=vid, title=title))

    return rows


def is_already_downloaded(out_dir: Path, video_id: str) -> bool:
    if not video_id:
        return False
    needle = f"[{video_id}]"
    for p in out_dir.glob(f"*{needle}.*"):
        if p.is_file():
            return True
    return False


def _download_opts(
    mode: DownloadMode,
    out_dir: Path,
    *,
    progress_cb: ProgressCallback | None = None,
    socket_timeout: int = 30,
    retries: int = 3,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    common = {
        "outtmpl": str(out_dir / "%(title).80s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": socket_timeout,
        "retries": retries,
    }
    if progress_cb:
        common["progress_hooks"] = [progress_cb]

    # If we shipped ffmpeg/ffprobe with the exe, point yt-dlp at them.
    ffdir = find_bundled_ffmpeg_dir()
    if ffdir:
        common["ffmpeg_location"] = str(ffdir)

    if mode == DownloadMode.AUDIO_MP3:
        return {
            **common,
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ],
        }

    if mode == DownloadMode.AUDIO_ORIGINAL:
        return {
            **common,
            "format": "bestaudio/best",
        }

    if mode == DownloadMode.VIDEO_ORIGINAL:
        return {
            **common,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }

    raise ValueError(f"Unsupported mode: {mode}")


def download_rows(
    rows: list[SearchRow],
    *,
    mode: DownloadMode,
    out_dir: Path,
    progress_cb: ProgressCallback | None = None,
    on_status: Callable[[str], None] | None = None,
    skip_existing: bool = False,
) -> None:
    ydl_opts = _download_opts(mode, out_dir, progress_cb=progress_cb)

    with YoutubeDL(ydl_opts) as ydl:
        for i, row in enumerate(rows, start=1):
            label = row.title or row.query or row.video_url
            if on_status:
                on_status(f"[{i}/{len(rows)}] {label}")

            if skip_existing and is_already_downloaded(out_dir, row.video_id):
                if on_status:
                    on_status("Skipping (already exists).")
                continue

            ydl.download([row.video_url])
            if on_status:
                on_status("Done.")
