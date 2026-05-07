from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import config
from core.downloader import DownloadWorker
from core.tool_manager import get_app_base_dir


class BatchJobRow(QFrame):
    """A single job row in the batch queue."""
    removed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("batch_job_row")
        self.setStyleSheet("""
            QFrame#batch_job_row {
                background-color: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # URL input
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Paste video URL here…")
        self._url_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._url_input.setAcceptDrops(True)

        # Custom filename (hidden by default)
        self._filename_input = QLineEdit()
        self._filename_input.setPlaceholderText("filename (optional)")
        self._filename_input.setFixedWidth(120)
        self._filename_input.setVisible(False)

        paste_btn = QPushButton("Paste")
        paste_btn.setFixedWidth(50)
        paste_btn.setObjectName("mini_btn")
        paste_btn.setStyleSheet("""
            QPushButton#mini_btn {
                background-color: #2a2a2a;
                color: #aaa;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton#mini_btn:hover { background-color: #383838; }
        """)
        paste_btn.clicked.connect(self._on_paste)

        # Format selector
        self._format_combo = QComboBox()
        self._format_combo.addItem("Video (MP4)", "video")
        self._format_combo.addItem("Audio", "audio")
        self._format_combo.setFixedWidth(140)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)

        # Quality selector (video only)
        self._quality_combo = QComboBox()
        self._quality_combo.addItem("Max", "max")
        self._quality_combo.setFixedWidth(80)
        self._quality_combo.setVisible(False)

        # FPS selector (video only)
        self._fps_combo = QComboBox()
        self._fps_combo.addItem("Max", "max")
        self._fps_combo.setFixedWidth(70)
        self._fps_combo.setVisible(False)

        # Audio codec selector
        self._codec_combo = QComboBox()
        self._codec_combo.addItem("MP3", "mp3")
        self._codec_combo.addItem("M4A (AAC)", "m4a")
        self._codec_combo.addItem("WAV (Lossless)", "wav")
        self._codec_combo.addItem("FLAC (Lossless)", "flac")
        self._codec_combo.addItem("OGG (Vorbis)", "vorbis")
        self._codec_combo.setFixedWidth(140)
        self._codec_combo.setVisible(False)

        # Audio bitrate selector (audio only)
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.addItem("Max", "max")
        self._bitrate_combo.setFixedWidth(70)
        self._bitrate_combo.setVisible(False)

        # Subtitle checkbox
        self._subtitle_check = QCheckBox("Subs")
        self._subtitle_check.setStyleSheet("color: #aaa; font-size: 11px;")

        # Playlist checkbox
        self._playlist_check = QCheckBox("Playlist")
        self._playlist_check.setStyleSheet("color: #aaa; font-size: 11px;")

        # Trim checkbox
        self._trim_check = QCheckBox("Trim")
        self._trim_check.setStyleSheet("color: #aaa; font-size: 11px;")
        self._trim_check.setToolTip("Trim video segment")
        self._trim_check.toggled.connect(self._on_trim_toggled)

        # Clear button
        clear_btn = QPushButton("×")
        clear_btn.setObjectName("mini_clear_btn")
        clear_btn.setFixedWidth(28)
        clear_btn.setFixedHeight(28)
        clear_btn.setStyleSheet("""
            QPushButton#mini_clear_btn {
                background-color: #2a2a2a;
                color: #aaa;
                border: none;
                border-radius: 3px;
                padding: 0px;
                font-size: 14px;
            }
            QPushButton#mini_clear_btn:hover { background-color: #383838; }
        """)
        clear_btn.clicked.connect(self._on_clear_url)

        # Delete button
        delete_btn = QPushButton("×")
        delete_btn.setObjectName("delete_btn")
        delete_btn.setFixedWidth(32)
        delete_btn.setFixedHeight(32)
        delete_btn.setStyleSheet("""
            QPushButton#delete_btn {
                background-color: #2a2a2a;
                color: #aaa;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton#delete_btn:hover { background-color: #b00020; color: #fff; }
        """)
        delete_btn.clicked.connect(self.removed.emit)

        layout.addWidget(self._url_input, stretch=1)
        layout.addWidget(paste_btn)
        layout.addWidget(clear_btn)
        layout.addWidget(self._filename_input)
        layout.addWidget(self._format_combo)
        layout.addWidget(self._quality_combo)
        layout.addWidget(self._fps_combo)
        layout.addWidget(self._codec_combo)
        layout.addWidget(self._bitrate_combo)
        layout.addWidget(self._subtitle_check)
        layout.addWidget(self._playlist_check)
        layout.addWidget(self._trim_check)
        layout.addWidget(delete_btn)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if text.startswith(("http://", "https://", "www.")):
                event.acceptProposedAction()

    def dropEvent(self, event):
        text = event.mimeData().text().strip()
        if text.startswith(("http://", "https://", "www.")):
            self._url_input.setText(text)
            event.acceptProposedAction()

    @Slot()
    def _on_paste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self._url_input.setText(text)

    @Slot()
    def _on_clear_url(self):
        self._url_input.clear()
        self._url_input.setFocus()

    @Slot(bool)
    def _on_trim_toggled(self, checked: bool):
        pass  # Trim in batch uses default 0,0 (no trim)

    @Slot()
    def _on_format_changed(self):
        is_audio = self._format_combo.currentData() == "audio"
        is_video = not is_audio
        # Video options
        self._quality_combo.setVisible(is_video)
        self._fps_combo.setVisible(is_video)
        # Audio options
        self._codec_combo.setVisible(is_audio)
        self._bitrate_combo.setVisible(is_audio)

    def get_data(self):
        """Return job configuration."""
        return {
            "url": self._url_input.text().strip(),
            "format_mode": self._format_combo.currentData(),
            "quality": self._quality_combo.currentData(),
            "fps": self._fps_combo.currentData(),
            "audio_codec": self._codec_combo.currentData(),
            "audio_bitrate": self._bitrate_combo.currentData(),
            "custom_filename": self._filename_input.text().strip(),
            "trim_start": None,  # Trim not implemented for batch
            "trim_end": None,
            "download_subtitles": self._subtitle_check.isChecked(),
            "download_playlist": self._playlist_check.isChecked(),
        }


class BatchWindow(QMainWindow):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state
        self._output_dir = str(config.DEFAULT_OUTPUT_DIR)
        self._download_worker = None
        self._current_job_index = 0
        self._jobs = []
        self._job_rows = []

        self._apply_dark_theme()
        self._build_ui()
        self.setWindowTitle("Batch Download")
        self.setMinimumSize(900, 700)

        # Set window icon
        icon_path = get_app_base_dir() / "image.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with output selector
        layout.addLayout(self._build_header_row())

        # Jobs scroll area
        layout.addWidget(self._build_jobs_section(), stretch=2)

        # Control buttons
        layout.addLayout(self._build_control_row())

        # Progress
        layout.addWidget(self._build_progress_section())

        # Log
        layout.addWidget(self._build_log_panel(), stretch=1)

        self.setCentralWidget(root)

    def _build_header_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        label = QLabel("Output Folder")
        label.setStyleSheet("color: #aaa; font-size: 12px;")
        label.setFixedWidth(90)

        self._output_label = QLineEdit()
        self._output_label.setText(self._output_dir)
        self._output_label.setReadOnly(True)
        self._output_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("secondary_btn")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._on_browse_output)

        row.addWidget(label)
        row.addWidget(self._output_label)
        row.addWidget(browse_btn)

        return row

    def _build_jobs_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        title = QLabel("Download Queue")
        title.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold;")
        layout.addWidget(title)

        # Scroll area for jobs
        scroll = QScrollArea()
        scroll.setObjectName("jobs_scroll")
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea#jobs_scroll {
                background-color: #0d0d0d;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
            }
        """)

        self._jobs_container = QWidget()
        self._jobs_layout = QVBoxLayout(self._jobs_container)
        self._jobs_layout.setContentsMargins(8, 8, 8, 8)
        self._jobs_layout.setSpacing(8)
        self._jobs_layout.addStretch()

        scroll.setWidget(self._jobs_container)
        layout.addWidget(scroll, stretch=1)

        # Add job button
        add_btn = QPushButton("+ Add Job")
        add_btn.setFixedHeight(36)
        add_btn.setObjectName("add_btn")
        add_btn.setStyleSheet("""
            QPushButton#add_btn {
                background-color: #2a2a2a;
                color: #aaa;
                border: 1px dashed #3a3a3a;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton#add_btn:hover { background-color: #383838; color: #fff; }
        """)
        add_btn.clicked.connect(self._add_job)
        layout.addWidget(add_btn)

        return widget

    def _build_control_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._start_btn = QPushButton("Start Batch Download")
        self._start_btn.setFixedHeight(40)
        self._start_btn.setFixedWidth(180)
        self._start_btn.clicked.connect(self._on_start_batch)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.setFixedHeight(40)
        self._cancel_btn.setFixedWidth(100)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._on_cancel_batch)

        row.addWidget(self._start_btn)
        row.addWidget(self._cancel_btn)
        row.addStretch()

        return row

    def _build_progress_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._job_counter = QLabel("Ready")
        self._job_counter.setStyleSheet("color: #aaa; font-size: 12px;")

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")

        layout.addWidget(self._job_counter)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._status_label)

        return widget

    def _build_log_panel(self) -> QTextEdit:
        log = QTextEdit()
        log.setReadOnly(True)
        log.setObjectName("log_panel")
        font = QFont()
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        log.setFont(font)
        return log

    def _apply_dark_theme(self):
        app = QApplication.instance()
        if app.style().objectName() != "Fusion":
            app.setStyle("Fusion")

        p = QPalette()
        bg = QColor("#121212")
        panel = QColor("#1e1e1e")
        text = QColor("#ffffff")
        accent = QColor("#6200ea")
        disabled_text = QColor("#666666")

        p.setColor(QPalette.Window, bg)
        p.setColor(QPalette.WindowText, text)
        p.setColor(QPalette.Base, panel)
        p.setColor(QPalette.AlternateBase, QColor("#2a2a2a"))
        p.setColor(QPalette.Text, text)
        p.setColor(QPalette.Button, panel)
        p.setColor(QPalette.ButtonText, text)
        p.setColor(QPalette.Highlight, accent)
        p.setColor(QPalette.HighlightedText, text)
        p.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
        p.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
        p.setColor(QPalette.PlaceholderText, QColor("#555555"))
        app.setPalette(p)

        app.setStyleSheet("""
            QMainWindow, QWidget#root {
                background-color: #121212;
            }
            QPushButton {
                background-color: #6200ea;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #7c4dff; }
            QPushButton:pressed { background-color: #3700b3; }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #555555;
            }
            QPushButton#secondary_btn {
                background-color: #2a2a2a;
                color: #aaaaaa;
                font-size: 12px;
                font-weight: normal;
            }
            QPushButton#secondary_btn:hover { background-color: #383838; }
            QPushButton#cancel_btn {
                background-color: #b00020;
                color: #ffffff;
                font-size: 12px;
            }
            QPushButton#cancel_btn:hover { background-color: #cf2040; }
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px 8px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #6200ea; }
            QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 5px 8px;
                color: #ffffff;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #aaaaaa;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                selection-background-color: #6200ea;
                color: #ffffff;
                outline: none;
            }
            QProgressBar {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #6200ea;
                border-radius: 3px;
            }
            QTextEdit#log_panel {
                background-color: #0d0d0d;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                color: #a0a0a0;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    def _add_job(self):
        """Add a new job row to the queue."""
        row = BatchJobRow()
        row.removed.connect(lambda: self._remove_job(row))
        self._job_rows.append(row)

        # Insert before the stretch
        self._jobs_layout.insertWidget(len(self._job_rows) - 1, row)

    def _remove_job(self, row: BatchJobRow):
        """Remove a job row from the queue."""
        if row in self._job_rows:
            index = self._job_rows.index(row)
            self._job_rows.remove(row)
            row.deleteLater()

    @Slot()
    def _on_browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self._output_dir
        )
        if directory:
            self._output_dir = directory
            self._output_label.setText(directory)

    @Slot()
    def _on_start_batch(self):
        """Start processing the batch queue."""
        if not self._job_rows:
            self._append_log("No jobs in queue. Add at least one job.")
            return

        # Collect all jobs
        self._jobs = []
        for row in self._job_rows:
            data = row.get_data()
            if not data["url"]:
                self._append_log(f"Skipping job with empty URL.")
                continue
            self._jobs.append(data)

        if not self._jobs:
            self._append_log("No valid jobs to process.")
            return

        self._current_job_index = 0
        self._set_ui_downloading(True)
        self._append_log(f"Starting batch download ({len(self._jobs)} job{'s' if len(self._jobs) != 1 else ''})…\n")
        self._start_next_job()

    @Slot()
    def _on_cancel_batch(self):
        """Cancel current download."""
        if self._download_worker is not None:
            self._download_worker.cancel()
            self._download_worker.requestInterruption()
            self._append_log("Cancelling current job…")
        self._jobs = []  # Clear remaining jobs
        self._current_job_index = 0

    def _start_next_job(self):
        """Start the next job in the queue."""
        # Clean up previous worker if it exists
        if self._download_worker is not None:
            self._download_worker.progress_update.disconnect()
            self._download_worker.status_update.disconnect()
            self._download_worker.download_complete.disconnect()
            self._download_worker.finished.disconnect()
            self._download_worker.deleteLater()

        if self._current_job_index >= len(self._jobs):
            # All jobs done
            self._download_worker = None
            self._set_ui_downloading(False)
            self._progress_bar.setValue(0)
            self._status_label.setText("")
            self._job_counter.setText("Complete")
            self._append_log(f"\nBatch download complete! Processed {len(self._jobs)} job{'s' if len(self._jobs) != 1 else ''}.")
            return

        job = self._jobs[self._current_job_index]
        job_num = self._current_job_index + 1
        total = len(self._jobs)

        self._job_counter.setText(f"{job_num}/{total}")
        self._append_log(f"Processing: {job['url'][:60]}…")
        self._progress_bar.setValue(0)

        self._download_worker = DownloadWorker(
            url=job["url"],
            output_dir=self._output_dir,
            format_mode=job["format_mode"],
            audio_codec=job["audio_codec"],
            download_subtitles=job["download_subtitles"],
            download_playlist=job["download_playlist"],
            custom_filename=job.get("custom_filename", ""),
            trim_start=job.get("trim_start"),
            trim_end=job.get("trim_end"),
            quality=job.get("quality", "max"),
            fps=job.get("fps", "max"),
            audio_bitrate=job.get("audio_bitrate", "max"),
            state=self._state,
        )
        self._download_worker.progress_update.connect(self._on_progress_update)
        self._download_worker.status_update.connect(self._on_status_update)
        self._download_worker.download_complete.connect(self._on_download_complete)
        self._download_worker.finished.connect(self._on_worker_finished)
        self._download_worker.start()

    @Slot(int, str)
    def _on_progress_update(self, pct: int, speed: str):
        self._progress_bar.setValue(pct)
        self._status_label.setText(speed)

    @Slot(str)
    def _on_status_update(self, message: str):
        self._append_log(message)

    @Slot(bool, str)
    def _on_download_complete(self, success: bool, message: str):
        self._progress_bar.setValue(100 if success else 0)
        self._append_log(message)
        self._current_job_index += 1
        self._start_next_job()

    @Slot()
    def _on_worker_finished(self):
        # Worker is already cleaned up in _start_next_job
        pass

    def _set_ui_downloading(self, active: bool):
        self._start_btn.setVisible(not active)
        self._cancel_btn.setVisible(active)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if text.startswith(("http://", "https://", "www.")):
                event.acceptProposedAction()

    def dropEvent(self, event):
        text = event.mimeData().text().strip()
        if text.startswith(("http://", "https://", "www.")):
            if self._job_rows:
                self._job_rows[-1]._url_input.setText(text)
            else:
                self._add_job()
                self._job_rows[-1]._url_input.setText(text)
            event.acceptProposedAction()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self._start_btn.isVisible():
                self._on_start_batch()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _append_log(self, message: str):
        if message:
            log_widget = self.findChild(QTextEdit, "log_panel")
            if log_widget:
                log_widget.append(message)
                log_widget.verticalScrollBar().setValue(
                    log_widget.verticalScrollBar().maximum()
                )
