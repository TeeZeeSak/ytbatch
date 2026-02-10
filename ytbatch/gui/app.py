from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QEvent
from PySide6.QtGui import QIcon, QGuiApplication, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QFrame,
    QDialog,
    QFormLayout,
)

from ytbatch.models import DownloadMode
from ytbatch.storage import default_base_run_dir
from ytbatch.gui.worker import JobConfig, ThreadRunner
from ytbatch.resources import resource_path


def open_folder(path: str) -> None:
    p = Path(path)
    if p.is_file():
        p = p.parent
    if not p.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{p}"')
    else:
        os.system(f'xdg-open "{p}"')


THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"


def system_prefers_dark() -> bool:
    try:
        cs = QGuiApplication.styleHints().colorScheme()
        return int(cs) == 2
    except Exception:
        pal = QApplication.palette()
        c = pal.color(QPalette.Window)
        return c.lightness() < 128


def make_dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(30, 30, 30))
    pal.setColor(QPalette.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.Base, QColor(22, 22, 22))
    pal.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
    pal.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    pal.setColor(QPalette.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.Button, QColor(45, 45, 45))
    pal.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    pal.setColor(QPalette.BrightText, QColor(255, 0, 0))
    pal.setColor(QPalette.Highlight, QColor(80, 140, 255))
    pal.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    return pal


def apply_theme(app: QApplication, theme: str) -> None:
    theme = (theme or THEME_SYSTEM).lower()
    if theme == THEME_LIGHT:
        app.setPalette(app.style().standardPalette())
    elif theme == THEME_DARK:
        app.setPalette(make_dark_palette())
    else:
        if system_prefers_dark():
            app.setPalette(make_dark_palette())
        else:
            app.setPalette(app.style().standardPalette())


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget, current_theme: str):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("System", THEME_SYSTEM)
        self.theme_combo.addItem("Light", THEME_LIGHT)
        self.theme_combo.addItem("Dark", THEME_DARK)

        idx = self.theme_combo.findData((current_theme or THEME_SYSTEM).lower())
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

        form = QFormLayout()
        form.addRow("Theme", self.theme_combo)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(row)
        self.setLayout(layout)

    def selected_theme(self) -> str:
        return str(self.theme_combo.currentData())


class DropOverlay(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()

        self.setStyleSheet(
            """
            QFrame {
                background: rgba(20, 20, 20, 160);
                border: 2px dashed rgba(255, 255, 255, 140);
                border-radius: 12px;
            }
            QLabel {
                color: rgba(255, 255, 255, 220);
                font-size: 18px;
                font-weight: 600;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)

        label = QLabel("Drop a .txt (queries) or .csv (output) file")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        sub = QLabel("• .txt will fill the query list\n• .csv will load the run directly")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 13px; font-weight: 400; color: rgba(255,255,255,180);")
        layout.addWidget(sub)

        layout.addStretch(1)

    def resize_to_parent(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        margin = 14
        self.setGeometry(
            margin,
            margin,
            max(0, parent.width() - margin * 2),
            max(0, parent.height() - margin * 2),
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ytbatch")
        self.resize(1000, 700)

        self.settings = QSettings("ytbatch", "ytbatch")
        self.runner: ThreadRunner | None = None
        self.last_csv_path: str | None = None

        icon_path = resource_path("icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Widgets
        self.queries_edit = QPlainTextEdit()
        self.queries_edit.setPlaceholderText("Paste queries here (one per line)...")

        self.mode_combo = QComboBox()
        for m in DownloadMode:
            self.mode_combo.addItem(m.value)

        self.skip_existing_chk = QCheckBox("Skip existing")
        self.skip_existing_chk.setChecked(bool(self.settings.value("skip_existing", True)))

        self.out_dir_edit = QLineEdit(self.settings.value("out_dir", str(Path("downloads").resolve())))
        self.run_dir_edit = QLineEdit(self.settings.value("run_dir", str(default_base_run_dir().resolve())))

        self.btn_browse_out = QPushButton("Browse…")
        self.btn_browse_run = QPushButton("Browse…")
        self.btn_load_list = QPushButton("Load list.txt…")
        self.btn_build_csv = QPushButton("Build CSV")
        self.btn_start = QPushButton("Start")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_open_run = QPushButton("Open run folder")
        self.btn_open_output = QPushButton("Open output folder")
        self.btn_open_run.setEnabled(False)
        self.btn_cancel.setEnabled(False)

        self.csv_label = QLabel("CSV: (not built yet)")
        self.status_label = QLabel("Status: idle")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Query", "Title", "URL", "Progress"])
        self.table.horizontalHeader().setStretchLastSection(True)

        # Layout
        central = QWidget()
        self.setCentralWidget(central)

        top = QGridLayout()
        top.addWidget(QLabel("Mode"), 0, 0)
        top.addWidget(self.mode_combo, 0, 1)
        top.addWidget(self.skip_existing_chk, 0, 2)

        top.addWidget(QLabel("Output folder"), 1, 0)
        top.addWidget(self.out_dir_edit, 1, 1)
        top.addWidget(self.btn_browse_out, 1, 2)

        top.addWidget(QLabel("Run folder base (CSV cache)"), 2, 0)
        top.addWidget(self.run_dir_edit, 2, 1)
        top.addWidget(self.btn_browse_run, 2, 2)

        btns = QHBoxLayout()
        btns.addWidget(self.btn_load_list)
        btns.addWidget(self.btn_build_csv)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_open_run)
        btns.addWidget(self.btn_open_output)
        btns.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(QLabel("Queries"))
        layout.addWidget(self.queries_edit, 2)
        layout.addLayout(btns)
        layout.addWidget(self.csv_label)
        layout.addWidget(self.table, 3)
        layout.addWidget(self.status_label)

        central.setLayout(layout)
        self.queries_edit.setAcceptDrops(False)
        self.table.setAcceptDrops(False)
        self.table.viewport().setAcceptDrops(False)
        self.status_label.setAcceptDrops(False)
        self.csv_label.setAcceptDrops(False)
        # Drag & drop overlay (MUST be created after central widget is set)
        self.setAcceptDrops(True)
        self.drop_overlay = DropOverlay(central)
        self.drop_overlay.resize_to_parent()
        self.drop_overlay.hide()
        self.installEventFilter(self)

        # Signals
        self.btn_browse_out.clicked.connect(self._browse_out)
        self.btn_browse_run.clicked.connect(self._browse_run)
        self.btn_load_list.clicked.connect(self._load_list)
        self.btn_build_csv.clicked.connect(self._build_csv_only)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_open_run.clicked.connect(self._open_run_folder)
        self.btn_open_output.clicked.connect(self._open_output_folder)

        #menu = self.menuBar().addMenu("Settings")
        #act = menu.addAction("Preferences…")
        #act.triggered.connect(self._open_settings)

    def _has_queries(self) -> bool:
        return len(self._collect_queries()) > 0
    
    def eventFilter(self, obj, event):
        if obj is self and event.type() == QEvent.Resize:
            if hasattr(self, "drop_overlay"):
                self.drop_overlay.resize_to_parent()
                self.drop_overlay.raise_()
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        self.settings.setValue("out_dir", self.out_dir_edit.text().strip())
        self.settings.setValue("run_dir", self.run_dir_edit.text().strip())
        self.settings.setValue("skip_existing", self.skip_existing_chk.isChecked())
        self.settings.setValue("theme", self.settings.value("theme", THEME_SYSTEM))
        super().closeEvent(event)

    def _open_settings(self) -> None:
        current = str(self.settings.value("theme", THEME_SYSTEM))
        dlg = SettingsDialog(self, current)
        if dlg.exec():
            theme = dlg.selected_theme()
            self.settings.setValue("theme", theme)
            app = QApplication.instance()
            if app is not None:
                apply_theme(app, theme)
            self._status(f"Theme set to: {theme}")

    def _browse_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select output folder", self.out_dir_edit.text())
        if d:
            self.out_dir_edit.setText(d)

    def _browse_run(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select base run folder", self.run_dir_edit.text())
        if d:
            self.run_dir_edit.setText(d)

    def _load_list(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open queries file", "", "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
            self.queries_edit.setPlainText(text)
            self._status(f"Loaded queries from: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _status(self, msg: str) -> None:
        self.status_label.setText(f"Status: {msg}")

    def _reset_table(self, lines: list[str]) -> None:
        self.table.setRowCount(0)
        for i, q in enumerate(lines, start=1):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(i)))
            self.table.setItem(r, 1, QTableWidgetItem(q))
            self.table.setItem(r, 2, QTableWidgetItem(""))
            self.table.setItem(r, 3, QTableWidgetItem(""))
            self.table.setItem(r, 4, QTableWidgetItem("0%"))

    def _collect_queries(self) -> list[str]:
        raw = self.queries_edit.toPlainText().splitlines()
        return [ln.strip() for ln in raw if ln.strip() and not ln.strip().startswith("#")]

    def _cfg(self) -> JobConfig:
        mode = DownloadMode(self.mode_combo.currentText())
        out_dir = Path(self.out_dir_edit.text().strip()).expanduser().resolve()
        base_run_dir = Path(self.run_dir_edit.text().strip()).expanduser().resolve()
        text = self.queries_edit.toPlainText()
        return JobConfig(
            mode=mode,
            out_dir=out_dir,
            base_run_dir=base_run_dir,
            queries_text=text,
            skip_existing=self.skip_existing_chk.isChecked(),
        )

    def _populate_from_csv(self, csv_path: str) -> None:
        try:
            raw = Path(csv_path).read_text(encoding="utf-8-sig", errors="replace")
        except Exception as e:
            self._status(f"Could not read CSV: {e}")
            return

        # Detect delimiter (common: comma or semicolon)
        first_line = raw.splitlines()[0] if raw.splitlines() else ""
        delimiter = ";" if first_line.count(";") > first_line.count(",") else ","

        try:
            with open(csv_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
        except Exception as e:
            self._status(f"Could not parse CSV: {e}")
            return

        # Debug-ish status
        headers = list(reader.fieldnames or []) if "reader" in locals() else []
        self._status(f"Loaded CSV ({len(rows)} rows), delimiter='{delimiter}', headers={headers}")

        # Accept either video_url or url
        def get_url(r: dict) -> str:
            return (r.get("video_url") or r.get("url") or r.get("video") or "").strip()

        def get_title(r: dict) -> str:
            return (r.get("title") or r.get("video_title") or "").strip()

        def get_query(r: dict) -> str:
            return (r.get("query") or r.get("search") or "").strip()

        lookup: dict[str, tuple[str, str]] = {}
        for r in rows:
            q = get_query(r)
            if not q:
                continue
            if q not in lookup:
                lookup[q] = (get_title(r), get_url(r))

        filled = 0
        for i in range(self.table.rowCount()):
            q_item = self.table.item(i, 1)
            if not q_item:
                continue
            q = q_item.text().strip()
            title, url = lookup.get(q, ("", ""))
            if title:
                self.table.setItem(i, 2, QTableWidgetItem(title))
            if url:
                self.table.setItem(i, 3, QTableWidgetItem(url))
            if title or url:
                filled += 1

        if filled == 0 and rows:
            # If nothing matched by query, try sequential fill as a fallback (same order)
            n = min(self.table.rowCount(), len(rows))
            for i in range(n):
                r = rows[i]
                title, url = get_title(r), get_url(r)
                if title:
                    self.table.setItem(i, 2, QTableWidgetItem(title))
                if url:
                    self.table.setItem(i, 3, QTableWidgetItem(url))
            self._status("CSV loaded but queries didn't match; filled sequentially as fallback.")


    def _wire_runner(self, runner: ThreadRunner) -> None:
        runner.worker.status.connect(self._status)
        runner.worker.csv_built.connect(self._on_csv_built)
        runner.worker.progress.connect(self._on_progress)
        runner.worker.finished.connect(self._on_finished)
        runner.worker.failed.connect(self._on_failed)

    def _on_csv_built(self, p: str) -> None:
        self.last_csv_path = p
        self.csv_label.setText(f"CSV: {p}")
        self.btn_open_run.setEnabled(True)
        self._populate_from_csv(p)

    def _open_run_folder(self) -> None:
        if self.last_csv_path:
            open_folder(self.last_csv_path)

    def _open_output_folder(self) -> None:
        out_path = self.out_dir_edit.text().strip()
        if not out_path:
            return
        open_folder(out_path)

    def _set_running(self, running: bool) -> None:
        self.btn_cancel.setEnabled(running)
        self.btn_start.setEnabled(not running)
        self.btn_build_csv.setEnabled(not running)
        self.btn_load_list.setEnabled(not running)

    def _build_csv_only(self) -> None:
        queries = self._collect_queries()
        if not queries:
            QMessageBox.information(self, "ytbatch", "No queries provided.")
            return
        self._reset_table(queries)

        cfg = self._cfg()
        self.runner = ThreadRunner(cfg)
        self._wire_runner(self.runner)
        self._set_running(True)

        def after_csv(_path: str) -> None:
            if self.runner:
                self.runner.worker.cancel()
                self._status("CSV built (download skipped).")

        self.runner.worker.csv_built.connect(after_csv)
        self.runner.thread.start()

    def _start(self) -> None:
        # If user pasted queries, we run the normal pipeline (build CSV -> download)
        if self._has_queries():
            queries = self._collect_queries()

            Path(self.out_dir_edit.text().strip()).mkdir(parents=True, exist_ok=True)
            self._reset_table(queries)

            self.runner = ThreadRunner(self._cfg())
            self._wire_runner(self.runner)
            self._set_running(True)
            self.runner.thread.start()
            return

        # Otherwise, if a CSV was dropped/loaded, download directly from it
        if self.last_csv_path and Path(self.last_csv_path).exists():
            Path(self.out_dir_edit.text().strip()).mkdir(parents=True, exist_ok=True)

            cfg = self._cfg()
            cfg.from_csv = Path(self.last_csv_path)

            self.runner = ThreadRunner(cfg)
            self._wire_runner(self.runner)
            self._set_running(True)
            self.runner.thread.start()
            self._status("Starting download from loaded CSV…")
            return

        QMessageBox.information(
            self,
            "ytbatch",
            "No queries provided and no CSV loaded.\n\nPaste queries, load a .txt, or drop an output.csv.",
        )

    def _cancel(self) -> None:
        if self.runner:
            self.runner.worker.cancel()
            self._status("Cancelling… (will stop after current item)")

    def _on_progress(self, idx: int, pct: float, text: str) -> None:
        if 0 <= idx < self.table.rowCount():
            self.table.setItem(idx, 4, QTableWidgetItem(f"{pct:0.1f}%  {text}"))

    def _on_finished(self) -> None:
        self._set_running(False)
        self._status("Finished.")
        self.runner = None

    def _on_failed(self, err: str) -> None:
        self._set_running(False)
        QMessageBox.critical(self, "ytbatch error", err)
        self._status("Failed.")
        self.runner = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                p = Path(u.toLocalFile())
                if p.suffix.lower() in (".txt", ".csv"):
                    event.acceptProposedAction()
                    self.drop_overlay.resize_to_parent()
                    self.drop_overlay.raise_()
                    self.drop_overlay.show()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_overlay.hide()
        event.accept()

    def dropEvent(self, event):
        self.drop_overlay.hide()

        urls = event.mimeData().urls()
        if not urls:
            return

        path = Path(urls[0].toLocalFile())
        if not path.exists():
            return

        if path.suffix.lower() == ".txt":
            try:
                text = path.read_text(encoding="utf-8-sig", errors="replace")
                self.queries_edit.setPlainText(text)
                self._status(f"Dropped queries file: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
            return

        if path.suffix.lower() == ".csv":
            self.last_csv_path = str(path)
            self.csv_label.setText(f"CSV: {path}")
            self.btn_open_run.setEnabled(True)

            # Build the table rows from the CSV queries first
            try:
                raw = path.read_text(encoding="utf-8-sig", errors="replace")
                first_line = raw.splitlines()[0] if raw.splitlines() else ""
                delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
                with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    queries = [(r.get("query") or "").strip() for r in reader if (r.get("query") or "").strip()]
            except Exception:
                queries = []

            if queries:
                self._reset_table(queries)

            self._populate_from_csv(str(path))
            self._status(f"Dropped CSV: {path}")
            return

        self._status(f"Ignored dropped file: {path.name}")


def main() -> None:
    app = QApplication(sys.argv)

    icon_path = resource_path("icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    s = QSettings("ytbatch", "ytbatch")
    apply_theme(app, str(s.value("theme", THEME_SYSTEM)))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
