from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ytbatch.core import build_run_csv, download_rows, load_rows_from_csv, normalize_query_lines, read_queries_file
from ytbatch.models import DownloadMode


def _progress_line(d: dict) -> None:
    status = d.get("status")
    if status == "downloading":
        downloaded = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        speed = d.get("speed") or 0
        eta = d.get("eta") or 0

        if total:
            pct = downloaded / total * 100.0
            msg = f"{pct:6.2f}%  {downloaded/1024/1024:7.2f}MB/{total/1024/1024:7.2f}MB"
        else:
            msg = f"{downloaded/1024/1024:7.2f}MB"

        if speed:
            msg += f"  {speed/1024/1024:5.2f}MB/s"
        if eta:
            msg += f"  ETA {eta:4d}s"

        print("\r" + msg.ljust(110), end="", flush=True)

    elif status == "finished":
        print("\rDownload finished. Post-processing...".ljust(110), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="ytbatch: build run CSV from queries and download with yt-dlp.")
    ap.add_argument("--mode", choices=[m.value for m in DownloadMode], default=DownloadMode.AUDIO_MP3.value)
    ap.add_argument("--out-dir", default="downloads", help="Output folder for downloaded files.")

    input_group = ap.add_mutually_exclusive_group(required=False)
    input_group.add_argument("--queries-file", help="Path to file containing one query per line.")
    input_group.add_argument("--query", action="append", help="A single query (repeatable).")
    input_group.add_argument("--from-csv", help="Skip search and download directly from an existing output.csv.")

    ap.add_argument(
        "--run-dir",
        default=None,
        help="Base directory for per-run folders (CSV). Default: per-user cache.",
    )
    ap.add_argument("--no-download", action="store_true", help="Only build the CSV; do not download.")
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip downloads if a file with the same [video_id] already exists in out-dir.",
    )

    args = ap.parse_args()
    mode = DownloadMode(args.mode)
    out_dir = Path(args.out_dir).expanduser().resolve()
    base_run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None

    def status(msg: str) -> None:
        print("\n" + msg, flush=True)

    try:
        if args.from_csv:
            csv_path = Path(args.from_csv).expanduser().resolve()
            rows = load_rows_from_csv(csv_path)
            if not rows:
                print(f"No downloadable rows found in {csv_path}", file=sys.stderr)
                return 2
            status(f"Loaded {len(rows)} rows from {csv_path}")

        else:
            if args.queries_file:
                queries = read_queries_file(Path(args.queries_file).expanduser().resolve())
            elif args.query:
                queries = normalize_query_lines(args.query)
            else:
                default = Path("list.txt")
                if default.exists():
                    queries = read_queries_file(default.resolve())
                else:
                    print("No input provided. Use --queries-file, --query, or --from-csv.", file=sys.stderr)
                    return 2

            run_paths, rows = build_run_csv(queries, base_run_dir=base_run_dir, on_status=status)
            status(f"Run folder: {run_paths.run_dir}")
            status(f"CSV saved:   {run_paths.csv_path}")
            status(f"Valid rows:  {len(rows)}")
            if not rows:
                return 0

        if args.no_download:
            status("Download skipped (--no-download).")
            return 0

        download_rows(
            rows,
            mode=mode,
            out_dir=out_dir,
            progress_cb=_progress_line,
            on_status=status,
            skip_existing=args.skip_existing,
        )
        status(f"All done. Output: {out_dir}")
        return 0

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
