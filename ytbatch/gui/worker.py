from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from ytbatch.core import build_run_csv, download_rows, load_rows_from_csv, normalize_query_lines, read_queries_file
from ytbatch.models import DownloadMode, SearchRow


@dataclass
class JobConfig:
    mode: DownloadMode
    out_dir: Path
    base_run_dir: Optional[Path] = None
    queries_file: Optional[Path] = None
    queries_text: Optional[str] = None
    from_csv: Optional[Path] = None
    skip_existing: bool = False


class Worker(QObject):
    status = Signal(str)
    progress = Signal(int, float, str)  # index (0-based), percent, text
    finished = Signal()
    failed = Signal(str)
    csv_built = Signal(str)  # path

    def __init__(self, cfg: JobConfig):
        super().__init__()
        self.cfg = cfg
        self._cancel = False
        self._rows: list[SearchRow] = []

    def cancel(self) -> None:
        self._cancel = True

    def _progress_hook_factory(self, row_index: int):
        def hook(d: dict) -> None:
            if self._cancel:
                return
            status = d.get("status")
            if status == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = (downloaded / total * 100.0) if total else 0.0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0
                text = f"{pct:5.1f}%"
                if speed:
                    text += f"  {speed/1024/1024:0.2f}MB/s"
                if eta:
                    text += f"  ETA {eta}s"
                self.progress.emit(row_index, float(pct), text)
            elif status == "finished":
                self.progress.emit(row_index, 100.0, "Post-processing...")
        return hook

    def run(self) -> None:
        try:
            if self.cfg.from_csv:
                self.status.emit(f"Loading CSV: {self.cfg.from_csv}")
                self._rows = load_rows_from_csv(self.cfg.from_csv)
                if not self._rows:
                    self.failed.emit("No downloadable rows found in CSV.")
                    return
            else:
                queries: list[str] = []
                if self.cfg.queries_file:
                    self.status.emit(f"Reading queries file: {self.cfg.queries_file}")
                    queries = read_queries_file(self.cfg.queries_file)
                elif self.cfg.queries_text is not None:
                    queries = normalize_query_lines(self.cfg.queries_text.splitlines())

                if not queries:
                    self.failed.emit("No queries provided.")
                    return

                run_paths, self._rows = build_run_csv(
                    queries,
                    base_run_dir=self.cfg.base_run_dir,
                    on_status=lambda s: self.status.emit(s),
                )
                self.csv_built.emit(str(run_paths.csv_path))
                self.status.emit(f"Run folder: {run_paths.run_dir}")
                self.status.emit(f"CSV: {run_paths.csv_path}")
                self.status.emit(f"Valid rows: {len(self._rows)}")
                if not self._rows:
                    self.finished.emit()
                    return

            for idx, row in enumerate(self._rows):
                if self._cancel:
                    self.status.emit("Cancelled.")
                    break
                label = row.title or row.query or row.video_url
                self.status.emit(f"[{idx+1}/{len(self._rows)}] {label}")

                download_rows(
                    [row],
                    mode=self.cfg.mode,
                    out_dir=self.cfg.out_dir,
                    progress_cb=self._progress_hook_factory(idx),
                    on_status=lambda s: self.status.emit(s),
                    skip_existing=self.cfg.skip_existing,
                )

            self.finished.emit()

        except Exception as e:
            self.failed.emit(str(e))


class ThreadRunner:
    def __init__(self, cfg: JobConfig):
        self.thread = QThread()
        self.worker = Worker(cfg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
