from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPalette, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QGroupBox,
    QDialog,
    QSpinBox,
)

from core import config
from core.bootstrap import BootstrapWorker
from core.downloader import DownloadWorker, InfoFetchWorker
from core.tool_manager import get_app_base_dir, patch_tools_path
from core.updater import IS_FROZEN, UpdateCheckWorker, UpdateDownloadWorker, apply_update
from core.version import __version__ as _VERSION
from ui_batch import BatchWindow
import subprocess
import sys


def _fmt_time(seconds: int) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


class RangeSlider(QWidget):
    range_changed = Signal(int, int)  # (start_seconds, end_seconds)

    _HR = 8   # handle radius px
    _TH = 5   # track height px

    _COLOR_TRACK      = QColor("#3a3a3a")
    _COLOR_ACTIVE     = QColor("#6200ea")
    _COLOR_HANDLE     = QColor("#ffffff")
    _COLOR_HANDLE_DIS = QColor("#666666")
    _COLOR_OUTLINE    = QColor("#2a2a2a")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._min = 0
        self._max = 0
        self._low = 0
        self._high = 0
        self._drag = None  # 'low' | 'high'
        self.setFixedHeight(28)
        self.setMinimumWidth(200)

    def set_range(self, min_val: int, max_val: int):
        self._min = min_val
        self._max = max(max_val, min_val + 1)
        self._low = min_val
        self._high = self._max
        self.update()
        self.range_changed.emit(self._low, self._high)

    @property
    def low(self) -> int:
        return self._low

    @property
    def high(self) -> int:
        return self._high

    def _val_to_x(self, val: int) -> int:
        r = self._HR
        span = self.width() - 2 * r
        if self._max == self._min or span <= 0:
            return r
        return r + int((val - self._min) / (self._max - self._min) * span)

    def _x_to_val(self, x: float) -> int:
        r = self._HR
        span = self.width() - 2 * r
        if span <= 0:
            return self._min
        ratio = max(0.0, min(1.0, (x - r) / span))
        return self._min + int(ratio * (self._max - self._min))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cy = self.height() // 2
        r, th = self._HR, self._TH

        # Background track
        p.setPen(Qt.NoPen)
        p.setBrush(self._COLOR_TRACK)
        p.drawRoundedRect(r, cy - th // 2, self.width() - 2 * r, th, th // 2, th // 2)

        # Active range highlight
        x_low = self._val_to_x(self._low)
        x_high = self._val_to_x(self._high)
        if x_high > x_low:
            p.setBrush(self._COLOR_ACTIVE if self.isEnabled() else self._COLOR_TRACK)
            p.drawRoundedRect(x_low, cy - th // 2, x_high - x_low, th, th // 2, th // 2)

        # Handles
        p.setBrush(self._COLOR_HANDLE if self.isEnabled() else self._COLOR_HANDLE_DIS)
        p.setPen(QPen(self._COLOR_OUTLINE, 1))
        p.drawEllipse(x_low - r, cy - r, 2 * r, 2 * r)
        p.drawEllipse(x_high - r, cy - r, 2 * r, 2 * r)
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return
        x = event.position().x()
        if abs(x - self._val_to_x(self._low)) <= abs(x - self._val_to_x(self._high)):
            self._drag = "low"
        else:
            self._drag = "high"
        self._apply_drag(x)

    def mouseMoveEvent(self, event):
        if self._drag:
            self._apply_drag(event.position().x())

    def mouseReleaseEvent(self, _event):
        self._drag = None

    def _apply_drag(self, x: float):
        val = self._x_to_val(x)
        if self._drag == "low":
            self._low = max(self._min, min(val, self._high - 1))
        else:
            self._high = min(self._max, max(val, self._low + 1))
        self.update()
        self.range_changed.emit(self._low, self._high)


class MainWindow(QMainWindow):
    def __init__(self, state):
        super().__init__()
        self._state = state
        self._bootstrap_worker = None
        self._download_worker = None
        self._output_dir = str(config.DEFAULT_OUTPUT_DIR)
        self._last_dl_pct = 0   # Fix 6: clamp progress bar against yt-dlp resets
        self._batch_window = None

        self._info_fetch_worker = None
        self._url_timer = QTimer(self)
        self._url_timer.setSingleShot(True)
        self._url_timer.setInterval(700)
        self._url_timer.timeout.connect(self._on_url_timer)

        self._update_check_worker = None
        self._update_download_worker = None
        self._update_url = None
        self._update_latest_version = None

        self._apply_dark_theme()
        self._build_ui()
        self.setWindowTitle("YT Downloader")
        self.setMinimumSize(750, 620)

        # Set window icon
        icon_path = get_app_base_dir() / "image.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Start background update check 3 s after launch (non-blocking)
        QTimer.singleShot(3000, self._start_update_check)

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
        layout.addLayout(self._build_saveas_row())
        layout.addLayout(self._build_format_row())
        layout.addLayout(self._build_options_row())
        layout.addLayout(self._build_segment_row())
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

        self._update_btn = QPushButton("Checking…")
        self._update_btn.setObjectName("secondary_btn")
        self._update_btn.setFixedWidth(200)
        self._update_btn.setEnabled(False)
        self._update_btn.setToolTip(f"Current version: v{_VERSION}")
        self._update_btn.clicked.connect(self._on_update_btn_clicked)

        layout.addWidget(self._ffmpeg_dot)
        layout.addWidget(self._ffmpeg_label)
        layout.addSpacing(8)
        layout.addWidget(self._deno_dot)
        layout.addWidget(self._deno_label)
        layout.addStretch()
        layout.addWidget(self._update_btn)

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
        self._url_input.textChanged.connect(self._on_url_text_changed)
        self._url_input.setAcceptDrops(True)

        paste_btn = QPushButton("Paste")
        paste_btn.setFixedWidth(60)
        paste_btn.setObjectName("secondary_btn")
        paste_btn.setToolTip("Paste from clipboard (Ctrl+V)")
        paste_btn.clicked.connect(self._on_paste_url)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.setObjectName("secondary_btn")
        clear_btn.setToolTip("Clear URL field")
        clear_btn.clicked.connect(self._on_clear_url)

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
        row.addWidget(paste_btn)
        row.addWidget(clear_btn)
        row.addWidget(browse_btn)
        row.addWidget(self._output_label)

        return row

    def _build_saveas_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        saveas_label = QLabel("Save as")
        saveas_label.setFixedWidth(48)
        saveas_label.setStyleSheet("color: #aaa; font-size: 12px;")

        self._saveas_input = QLineEdit()
        self._saveas_input.setPlaceholderText("%(title)s [%(id)s].%(ext)s  (leave empty for default)")
        self._saveas_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        row.addWidget(saveas_label)
        row.addWidget(self._saveas_input)

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

        self._quality_label = QLabel("Quality")
        self._quality_label.setFixedWidth(48)
        self._quality_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self._quality_label.setVisible(False)

        self._quality_combo = QComboBox()
        self._quality_combo.addItem("Max", "max")
        self._quality_combo.setFixedWidth(100)
        self._quality_combo.setVisible(False)

        self._fps_label = QLabel("FPS")
        self._fps_label.setFixedWidth(32)
        self._fps_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self._fps_label.setVisible(False)

        self._fps_combo = QComboBox()
        self._fps_combo.addItem("Max", "max")
        self._fps_combo.setFixedWidth(90)
        self._fps_combo.setVisible(False)

        self._download_btn = QPushButton("Download")
        self._download_btn.setEnabled(False)
        self._download_btn.setFixedWidth(110)
        self._download_btn.clicked.connect(self._on_download_clicked)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.setFixedWidth(80)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)

        batch_btn = QPushButton("Batch…")
        batch_btn.setObjectName("secondary_btn")
        batch_btn.setFixedWidth(80)
        batch_btn.clicked.connect(self._on_batch_clicked)

        row.addWidget(fmt_label)
        row.addWidget(self._format_combo)
        row.addWidget(self._quality_label)
        row.addWidget(self._quality_combo)
        row.addWidget(self._fps_label)
        row.addWidget(self._fps_combo)
        row.addWidget(self._download_btn)
        row.addWidget(self._cancel_btn)
        row.addWidget(batch_btn)
        row.addStretch()

        return row

    def _build_options_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        # Audio codec selector (shown only for audio format)
        self._codec_label = QLabel("Audio Codec")
        self._codec_label.setFixedWidth(80)
        self._codec_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self._codec_label.setVisible(False)

        self._codec_combo = QComboBox()
        self._codec_combo.addItem("MP3", "mp3")
        self._codec_combo.addItem("M4A (AAC)", "m4a")
        self._codec_combo.addItem("WAV (Lossless)", "wav")
        self._codec_combo.addItem("FLAC (Lossless)", "flac")
        self._codec_combo.addItem("OGG (Vorbis)", "vorbis")
        self._codec_combo.setFixedWidth(160)
        self._codec_combo.setVisible(False)

        self._bitrate_label = QLabel("Bitrate")
        self._bitrate_label.setFixedWidth(50)
        self._bitrate_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self._bitrate_label.setVisible(False)

        self._bitrate_combo = QComboBox()
        self._bitrate_combo.addItem("Max", "max")
        self._bitrate_combo.setFixedWidth(90)
        self._bitrate_combo.setVisible(False)

        # Subtitle checkbox
        self._subtitle_check = QCheckBox("Download Subtitles")
        self._subtitle_check.setStyleSheet("color: #aaa; font-size: 12px;")

        # Playlist checkbox
        self._playlist_check = QCheckBox("Download Playlist")
        self._playlist_check.setStyleSheet("color: #aaa; font-size: 12px;")

        row.addWidget(self._codec_label)
        row.addWidget(self._codec_combo)
        row.addWidget(self._bitrate_label)
        row.addWidget(self._bitrate_combo)
        row.addWidget(self._subtitle_check)
        row.addWidget(self._playlist_check)
        row.addStretch()

        return row

    def _build_segment_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._segment_check = QCheckBox("Trim")
        self._segment_check.setStyleSheet("color: #aaa; font-size: 12px;")
        self._segment_check.setToolTip("Download only a segment of the video")
        self._segment_check.toggled.connect(self._on_segment_toggled)

        self._range_slider = RangeSlider()
        self._range_slider.setEnabled(False)
        self._range_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._range_slider.range_changed.connect(self._on_range_changed)

        self._segment_label = QLabel("--:-- – --:--")
        self._segment_label.setStyleSheet("color: #666; font-size: 11px;")
        self._segment_label.setFixedWidth(115)
        self._segment_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._segment_fetch_label = QLabel("")
        self._segment_fetch_label.setStyleSheet("color: #555; font-size: 10px;")
        self._segment_fetch_label.setFixedWidth(70)

        row.addWidget(self._segment_check)
        row.addWidget(self._range_slider, stretch=1)
        row.addWidget(self._segment_label)
        row.addWidget(self._segment_fetch_label)

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

        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet("color: #666; font-size: 11px;")

        self._open_folder_btn = QPushButton("Open Folder")
        self._open_folder_btn.setFixedWidth(100)
        self._open_folder_btn.setObjectName("secondary_btn")
        self._open_folder_btn.setVisible(False)
        self._open_folder_btn.clicked.connect(self._on_open_folder)

        info_row.addWidget(self._speed_label)
        info_row.addStretch()
        info_row.addWidget(self._open_folder_btn)

        layout.addWidget(self._progress_bar)
        layout.addLayout(info_row)

        return widget

    def _build_log_panel(self) -> QPlainTextEdit:
        self._log = QPlainTextEdit()
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
            QPlainTextEdit#log_panel {
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
            patch_tools_path()
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
    # Update checking
    # ------------------------------------------------------------------ #

    def _start_update_check(self):
        if not IS_FROZEN:
            self._update_btn.setText("Running from source")
            self._update_btn.setEnabled(True)
            self._update_btn.setToolTip(
                f"v{_VERSION} (source) — run git pull to update"
            )
            return

        if self._update_check_worker is not None:
            return

        self._update_check_worker = UpdateCheckWorker(self)
        self._update_check_worker.update_available.connect(self._on_update_found)
        self._update_check_worker.up_to_date.connect(self._on_up_to_date)
        self._update_check_worker.check_failed.connect(self._on_update_check_failed)
        self._update_check_worker.finished.connect(self._on_update_check_finished)
        self._update_check_worker.start()

    @Slot(str, str)
    def _on_update_found(self, latest: str, url: str):
        self._update_latest_version = latest
        self._update_url = url
        self._update_btn.setText(f"Update to v{latest}")
        self._update_btn.setEnabled(True)
        self._update_btn.setToolTip(
            f"v{latest} is available (current: v{_VERSION}) — click to update"
        )
        # Switch to purple by clearing the secondary_btn objectName
        self._update_btn.setObjectName("")
        self._update_btn.style().unpolish(self._update_btn)
        self._update_btn.style().polish(self._update_btn)

    @Slot(str)
    def _on_up_to_date(self, latest: str):
        self._update_url = ""   # sentinel: checked and up to date
        self._update_btn.setText("Up to date")
        self._update_btn.setEnabled(True)
        self._update_btn.setToolTip(f"v{_VERSION} is the latest version")

    @Slot(str)
    def _on_update_check_failed(self, error: str):
        self._update_btn.setText("Check for updates")
        self._update_btn.setEnabled(True)
        self._update_btn.setToolTip(f"Update check failed: {error}\nClick to retry")

    @Slot()
    def _on_update_check_finished(self):
        worker = self._update_check_worker
        self._update_check_worker = None
        if worker is not None:
            worker.deleteLater()

    @Slot()
    def _on_update_btn_clicked(self):
        if not IS_FROZEN:
            QMessageBox.information(
                self, "Running from source",
                f"Current version: v{_VERSION}\n\n"
                "You're running from source. To update, run:\n\n    git pull",
            )
            return

        if self._update_url is None:
            # Check failed or not yet run — retry
            self._update_btn.setText("Checking…")
            self._update_btn.setEnabled(False)
            self._update_check_worker = None
            self._start_update_check()
            return

        if self._update_url == "":
            # Already up to date
            QMessageBox.information(
                self, "Up to date",
                f"v{_VERSION} is the latest version.",
            )
            return

        # Update available — confirm
        reply = QMessageBox.question(
            self, "Update available",
            f"Version v{self._update_latest_version} is available.\n"
            f"Current version: v{_VERSION}\n\n"
            "Download and install now?\n"
            "The app will restart automatically.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        self._update_btn.setText("Downloading…")
        self._update_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._speed_label.setText("Downloading update…")

        self._update_download_worker = UpdateDownloadWorker(self._update_url, self)
        self._update_download_worker.progress.connect(self._on_update_progress)
        self._update_download_worker.finished.connect(self._on_update_downloaded)
        self._update_download_worker.failed.connect(self._on_update_download_failed)
        self._update_download_worker.start()

    @Slot(int)
    def _on_update_progress(self, pct: int):
        self._progress_bar.setValue(pct)
        self._speed_label.setText(f"Downloading update… {pct}%")

    @Slot(str)
    def _on_update_downloaded(self, tmp_path: str):
        worker = self._update_download_worker
        self._update_download_worker = None
        if worker is not None:
            worker.deleteLater()

        self._progress_bar.setValue(0)
        self._speed_label.setText("")

        QMessageBox.information(
            self, "Restarting",
            "Update downloaded. The app will now restart to apply it.",
        )
        apply_update(tmp_path)

    @Slot(str)
    def _on_update_download_failed(self, error: str):
        worker = self._update_download_worker
        self._update_download_worker = None
        if worker is not None:
            worker.deleteLater()

        self._progress_bar.setValue(0)
        self._speed_label.setText("")
        self._update_btn.setText(f"Update to v{self._update_latest_version}")
        self._update_btn.setEnabled(True)
        QMessageBox.critical(self, "Update failed", f"Download error:\n{error}")

    # ------------------------------------------------------------------ #
    # Slots — URL / info fetch
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_paste_url(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self._url_input.setText(text)
            self._url_input.setFocus()

    @Slot()
    def _on_clear_url(self):
        self._url_input.clear()
        self._url_input.setFocus()

    @Slot()
    def _on_url_text_changed(self):
        self._url_timer.stop()
        if self._url_input.text().strip():
            self._segment_fetch_label.setText("…")
            self._url_timer.start()
        else:
            self._segment_fetch_label.setText("")
            self._range_slider.set_range(0, 0)
            self._segment_label.setText("--:-- – --:--")
            self._range_slider.setEnabled(False)

    @Slot()
    def _on_url_timer(self):
        url = self._url_input.text().strip()
        if not url:
            return
        # Disconnect stale worker signals before replacing
        if self._info_fetch_worker is not None:
            try:
                self._info_fetch_worker.duration_fetched.disconnect()
                self._info_fetch_worker.formats_found.disconnect()
                self._info_fetch_worker.fps_found.disconnect()
                self._info_fetch_worker.bitrates_found.disconnect()
                self._info_fetch_worker.fetch_failed.disconnect()
                self._info_fetch_worker.finished.disconnect()
            except Exception:
                pass
        worker = InfoFetchWorker(url, self._state)
        self._info_fetch_worker = worker
        worker.duration_fetched.connect(self._on_duration_fetched)
        worker.formats_found.connect(self._on_formats_found)
        worker.fps_found.connect(self._on_fps_found)
        worker.bitrates_found.connect(self._on_bitrates_found)
        worker.fetch_failed.connect(self._on_duration_fetch_failed)
        worker.finished.connect(self._on_info_fetch_finished)
        worker.start()

    @Slot(int)
    def _on_duration_fetched(self, duration: int):
        self._segment_fetch_label.setText("")
        self._range_slider.set_range(0, duration)
        self._range_slider.setEnabled(self._segment_check.isChecked())
        self._segment_label.setText(f"00:00 – {_fmt_time(duration)}")

    @Slot(list)
    def _on_formats_found(self, heights: list):
        self._quality_combo.blockSignals(True)
        self._quality_combo.clear()
        self._quality_combo.addItem("Max", "max")
        for h in heights:
            self._quality_combo.addItem(f"{h}p", str(h))
        self._quality_combo.blockSignals(False)

    @Slot(list)
    def _on_fps_found(self, fps_list: list):
        self._fps_combo.blockSignals(True)
        self._fps_combo.clear()
        self._fps_combo.addItem("Max", "max")
        for fps in fps_list:
            self._fps_combo.addItem(f"{fps}fps", str(fps))
        self._fps_combo.blockSignals(False)

    @Slot(list)
    def _on_bitrates_found(self, bitrates: list):
        self._bitrate_combo.blockSignals(True)
        self._bitrate_combo.clear()
        self._bitrate_combo.addItem("Max", "max")
        for br in bitrates:
            self._bitrate_combo.addItem(f"{br}k", str(br))
        self._bitrate_combo.blockSignals(False)

    @Slot(str)
    def _on_duration_fetch_failed(self, _error: str):
        self._segment_fetch_label.setText("")

    @Slot()
    def _on_info_fetch_finished(self):
        worker = self._info_fetch_worker
        self._info_fetch_worker = None
        if worker is not None:
            worker.deleteLater()

    @Slot(bool)
    def _on_segment_toggled(self, checked: bool):
        has_range = self._range_slider._max > 0
        self._range_slider.setEnabled(checked and has_range)

    @Slot(int, int)
    def _on_range_changed(self, low: int, high: int):
        self._segment_label.setText(f"{_fmt_time(low)} – {_fmt_time(high)}")

    # ------------------------------------------------------------------ #
    # Slots — download controls
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_format_changed(self):
        is_audio = self._format_combo.currentData() == "audio"
        self._codec_label.setVisible(is_audio)
        self._codec_combo.setVisible(is_audio)
        self._bitrate_label.setVisible(is_audio)
        self._bitrate_combo.setVisible(is_audio)
        is_video = not is_audio
        self._quality_label.setVisible(is_video)
        self._quality_combo.setVisible(is_video)
        self._fps_label.setVisible(is_video)
        self._fps_combo.setVisible(is_video)

    @Slot()
    def _on_batch_clicked(self):
        if self._batch_window is None:
            self._batch_window = BatchWindow(self._state, self)
            self._batch_window.destroyed.connect(self._on_batch_window_closed)
        self._batch_window.show()
        self._batch_window.raise_()
        self._batch_window.activateWindow()

    @Slot()
    def _on_batch_window_closed(self):
        self._batch_window = None

    @Slot()
    def _on_open_folder(self):
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{self._output_dir}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", self._output_dir])
        else:
            subprocess.Popen(["xdg-open", self._output_dir])

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
        if success:
            self._open_folder_btn.setVisible(True)

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

        trim_start = None
        trim_end = None
        if self._segment_check.isChecked() and self._range_slider._max > 0:
            trim_start = self._range_slider.low
            trim_end = self._range_slider.high

        self._download_worker = DownloadWorker(
            url=url,
            output_dir=self._output_dir,
            format_mode=self._format_combo.currentData(),
            audio_codec=self._codec_combo.currentData(),
            download_subtitles=self._subtitle_check.isChecked(),
            download_playlist=self._playlist_check.isChecked(),
            custom_filename=self._saveas_input.text().strip(),
            trim_start=trim_start,
            trim_end=trim_end,
            quality=self._quality_combo.currentData(),
            fps=self._fps_combo.currentData(),
            audio_bitrate=self._bitrate_combo.currentData(),
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
        self._saveas_input.setEnabled(not active)
        self._format_combo.setEnabled(not active)
        self._codec_combo.setEnabled(not active)
        self._quality_combo.setEnabled(not active)
        self._fps_combo.setEnabled(not active)
        self._bitrate_combo.setEnabled(not active)
        self._segment_check.setEnabled(not active)
        if active:
            self._range_slider.setEnabled(False)
            self._open_folder_btn.setVisible(False)
        else:
            self._range_slider.setEnabled(
                self._segment_check.isChecked() and self._range_slider._max > 0
            )

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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self._url_input.hasFocus() or self.focusWidget() in [
                self._format_combo, self._quality_combo, self._fps_combo,
                self._codec_combo, self._bitrate_combo
            ]:
                self._on_download_clicked()
            else:
                super().keyPressEvent(event)
        elif event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            if self._url_input.hasFocus():
                self._on_paste_url()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _append_log(self, message: str):
        if message:
            self._log.appendPlainText(message)
            self._log.moveCursor(QTextCursor.End)
