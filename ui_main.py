from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from core import config
from core.bootstrap import BootstrapWorker
from core.downloader import DownloadWorker
from core.tool_manager import get_app_base_dir


class MainWindow(QMainWindow):
    def __init__(self, state):
        super().__init__()
        self._state = state
        self._bootstrap_worker = None
        self._download_worker = None
        self._output_dir = str(config.DEFAULT_OUTPUT_DIR)
        self._last_dl_pct = 0   # Fix 6: clamp progress bar against yt-dlp resets

        self._apply_dark_theme()
        self._build_ui()
        self.setWindowTitle("YT Downloader")
        self.setMinimumSize(750, 620)

        # Set window icon
        icon_path = get_app_base_dir() / "image.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_tool_panel())
        layout.addLayout(self._build_url_row())
        layout.addLayout(self._build_format_row())
        layout.addLayout(self._build_options_row())
        layout.addWidget(self._build_progress_section())
        layout.addWidget(self._build_log_panel(), stretch=1)

        self.setCentralWidget(root)

    def _build_tool_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("tool_status_panel")
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(24)

        self._ffmpeg_dot = QLabel("●")
        self._ffmpeg_dot.setStyleSheet("color: #888; font-size: 14px;")
        self._ffmpeg_label = QLabel("ffmpeg: Checking…")
        self._ffmpeg_label.setStyleSheet("color: #aaa; font-size: 12px;")

        self._deno_dot = QLabel("●")
        self._deno_dot.setStyleSheet("color: #888; font-size: 14px;")
        self._deno_label = QLabel("deno: Checking…")
        self._deno_label.setStyleSheet("color: #aaa; font-size: 12px;")

        layout.addWidget(self._ffmpeg_dot)
        layout.addWidget(self._ffmpeg_label)
        layout.addSpacing(8)
        layout.addWidget(self._deno_dot)
        layout.addWidget(self._deno_label)
        layout.addStretch()

        return frame

    def _build_url_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        url_label = QLabel("URL")
        url_label.setFixedWidth(32)
        url_label.setStyleSheet("color: #aaa; font-size: 12px;")

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Paste video URL here…")
        self._url_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        browse_btn = QPushButton("Output…")
        browse_btn.setFixedWidth(80)
        browse_btn.setObjectName("secondary_btn")
        browse_btn.clicked.connect(self._on_browse_output)

        self._output_label = QLabel(self._output_dir)
        self._output_label.setStyleSheet("color: #666; font-size: 10px;")
        self._output_label.setMaximumWidth(200)
        self._output_label.setWordWrap(False)
        self._output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        row.addWidget(url_label)
        row.addWidget(self._url_input)
        row.addWidget(browse_btn)
        row.addWidget(self._output_label)

        return row

    def _build_format_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        fmt_label = QLabel("Format")
        fmt_label.setFixedWidth(48)
        fmt_label.setStyleSheet("color: #aaa; font-size: 12px;")

        self._format_combo = QComboBox()
        self._format_combo.addItem("Video (MP4)", "video")
        self._format_combo.addItem("Audio", "audio")
        self._format_combo.setFixedWidth(140)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)

        self._download_btn = QPushButton("Download")
        self._download_btn.setEnabled(False)
        self._download_btn.setFixedWidth(110)
        self._download_btn.clicked.connect(self._on_download_clicked)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.setFixedWidth(80)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)

        row.addWidget(fmt_label)
        row.addWidget(self._format_combo)
        row.addWidget(self._download_btn)
        row.addWidget(self._cancel_btn)
        row.addStretch()

        return row

    def _build_options_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        # Audio codec selector (shown only for audio format)
        codec_label = QLabel("Audio Codec")
        codec_label.setFixedWidth(80)
        codec_label.setStyleSheet("color: #aaa; font-size: 12px;")

        self._codec_combo = QComboBox()
        self._codec_combo.addItem("MP3", "mp3")
        self._codec_combo.addItem("M4A (AAC)", "m4a")
        self._codec_combo.addItem("WAV (Lossless)", "wav")
        self._codec_combo.addItem("FLAC (Lossless)", "flac")
        self._codec_combo.addItem("OGG (Vorbis)", "vorbis")
        self._codec_combo.setFixedWidth(160)
        self._codec_combo.setVisible(False)

        # Subtitle checkbox
        self._subtitle_check = QCheckBox("Download Subtitles")
        self._subtitle_check.setStyleSheet("color: #aaa; font-size: 12px;")

        row.addWidget(codec_label)
        row.addWidget(self._codec_combo)
        row.addWidget(self._subtitle_check)
        row.addStretch()

        return row

    def _build_progress_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")

        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet("color: #666; font-size: 11px;")

        layout.addWidget(self._progress_bar)
        layout.addWidget(self._speed_label)

        return widget

    def _build_log_panel(self) -> QTextEdit:
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setObjectName("log_panel")
        font = QFont()
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self._log.setFont(font)
        return self._log

    # ------------------------------------------------------------------ #
    # Theme
    # ------------------------------------------------------------------ #

    def _apply_dark_theme(self):
        app = QApplication.instance()
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
            QFrame#tool_status_panel {
                background-color: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
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

    # ------------------------------------------------------------------ #
    # Bootstrap
    # ------------------------------------------------------------------ #

    def start_bootstrap(self):
        self._bootstrap_worker = BootstrapWorker(self._state)
        self._bootstrap_worker.tool_status_changed.connect(self._on_tool_status_changed)
        self._bootstrap_worker.tool_progress.connect(self._on_bootstrap_progress)
        self._bootstrap_worker.bootstrap_complete.connect(self._on_bootstrap_complete)
        self._bootstrap_worker.log_message.connect(self._append_log)
        # Release reference only in finished — guaranteed to fire after run() returns
        self._bootstrap_worker.finished.connect(self._on_bootstrap_finished)
        self._bootstrap_worker.start()

    # ------------------------------------------------------------------ #
    # Slots — bootstrap
    # ------------------------------------------------------------------ #

    @Slot(str, str)
    def _on_tool_status_changed(self, tool: str, status: str):
        ready = status == "Ready"
        failed = status == "Failed"
        color = "#00c853" if ready else ("#f44336" if failed else "#ffa000")

        if tool == "ffmpeg":
            self._ffmpeg_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            self._ffmpeg_label.setText(f"ffmpeg: {status}")
        elif tool == "deno":
            self._deno_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            self._deno_label.setText(f"deno: {status}")

    @Slot(str, int)
    def _on_bootstrap_progress(self, tool: str, pct: int):
        self._progress_bar.setValue(pct)
        self._speed_label.setText(f"Downloading {tool}… {pct}%")

    @Slot(bool, str)
    def _on_bootstrap_complete(self, success: bool, message: str):
        # UI-only updates here — do NOT touch self._bootstrap_worker; run() may not have
        # returned yet when this queued slot fires on the main thread.
        self._progress_bar.setValue(0)
        self._speed_label.setText("")
        if success:
            self._download_btn.setEnabled(True)
            self._append_log("All tools ready. You can start downloading.")
        else:
            self._append_log(f"Bootstrap failed: {message}")
            self._append_log("Some features may not work without ffmpeg.")

    @Slot()
    def _on_bootstrap_finished(self):
        # Qt emits finished only after run() has returned — safe to release reference here.
        worker = self._bootstrap_worker
        self._bootstrap_worker = None
        if worker is not None:
            worker.deleteLater()

    # ------------------------------------------------------------------ #
    # Slots — download controls
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_format_changed(self):
        is_audio = self._format_combo.currentData() == "audio"
        self._codec_combo.setVisible(is_audio)

    @Slot()
    def _on_download_clicked(self):
        url = self._url_input.text().strip()
        if not url:
            self._append_log("Please enter a URL.")
            return
        if self._state.download_active:
            return
        self._start_download(url)

    @Slot()
    def _on_cancel_clicked(self):
        if self._download_worker is not None:
            self._download_worker.cancel()
            self._download_worker.requestInterruption()
            self._append_log("Cancelling…")

    @Slot()
    def _on_browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self._output_dir
        )
        if directory:
            self._output_dir = directory
            self._output_label.setText(directory)

    # ------------------------------------------------------------------ #
    # Slots — worker signals
    # ------------------------------------------------------------------ #

    @Slot(int, str)
    def _on_progress_update(self, pct: int, speed: str):
        # Fix 6: only advance — never let the bar drift backwards for multi-part downloads
        if pct >= self._last_dl_pct:
            self._last_dl_pct = pct
            self._progress_bar.setValue(pct)
        self._speed_label.setText(speed)

    @Slot(str)
    def _on_status_update(self, message: str):
        self._append_log(message)

    @Slot(bool, str)
    def _on_download_complete(self, success: bool, message: str):
        # UI-only updates here — do NOT touch self._download_worker; run() may not have
        # returned yet when this queued slot fires on the main thread.
        self._state.download_active = False
        self._set_ui_downloading(False)
        self._progress_bar.setValue(0)
        self._speed_label.setText("")
        self._append_log(message)

    @Slot()
    def _on_worker_finished(self):
        # Qt emits finished only after run() has returned — safe to release reference here.
        worker = self._download_worker
        self._download_worker = None
        if worker is not None:
            worker.deleteLater()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _start_download(self, url: str):
        self._state.download_active = True
        self._set_ui_downloading(True)
        self._last_dl_pct = 0   # Fix 6: reset clamp for new download
        self._progress_bar.setValue(0)
        self._log.clear()
        self._append_log(f"Starting download: {url}")

        self._download_worker = DownloadWorker(
            url=url,
            output_dir=self._output_dir,
            format_mode=self._format_combo.currentData(),
            audio_codec=self._codec_combo.currentData(),
            download_subtitles=self._subtitle_check.isChecked(),
            state=self._state,
        )
        self._download_worker.progress_update.connect(self._on_progress_update)
        self._download_worker.status_update.connect(self._on_status_update)
        self._download_worker.download_complete.connect(self._on_download_complete)
        # Release reference only in finished — guaranteed to fire after run() returns
        self._download_worker.finished.connect(self._on_worker_finished)
        self._download_worker.start()

    def _set_ui_downloading(self, active: bool):
        self._download_btn.setVisible(not active)
        self._cancel_btn.setVisible(active)
        self._url_input.setEnabled(not active)
        self._format_combo.setEnabled(not active)

    def _append_log(self, message: str):
        if message:
            self._log.append(message)
            self._log.verticalScrollBar().setValue(
                self._log.verticalScrollBar().maximum()
            )
