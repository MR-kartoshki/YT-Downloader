import os
from pathlib import Path

import yt_dlp
from PySide6.QtCore import QThread, Signal

from core import config
from core.tool_manager import get_tools_dir


class DownloadWorker(QThread):
    progress_update = Signal(int, str)    # (percent 0-100, speed_string)
    status_update = Signal(str)           # log lines
    download_complete = Signal(bool, str) # (success, message)

    def __init__(self, url: str, output_dir: str, format_mode: str, audio_codec: str,
                 download_subtitles: bool, state, parent=None):
        super().__init__(parent)
        self._url = url
        self._output_dir = Path(output_dir)
        self._format_mode = format_mode  # 'video' or 'audio'
        self._audio_codec = audio_codec  # 'mp3', 'm4a', 'wav', 'flac', 'vorbis'
        self._download_subtitles = download_subtitles
        self._state = state
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        # Add tools dir to PATH so yt-dlp can find deno and ffmpeg
        tools_dir = str(get_tools_dir())
        old_path = os.environ.get("PATH", "")
        path_sep = ";" if os.name == "nt" else ":"
        os.environ["PATH"] = f"{tools_dir}{path_sep}{old_path}"

        # Fix 7: download_complete is always emitted, regardless of how run() exits.
        try:
            try:
                opts = self._build_ydl_opts()
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([self._url])
                if self._stop:
                    self.download_complete.emit(False, "Cancelled.")
                else:
                    self.download_complete.emit(True, "Download complete.")
            except yt_dlp.utils.DownloadCancelled:
                self.download_complete.emit(False, "Cancelled.")
            except Exception as e:
                if self._stop:
                    self.download_complete.emit(False, "Cancelled.")
                else:
                    self.download_complete.emit(False, str(e))
        finally:
            # Restore original PATH
            os.environ["PATH"] = old_path

    def _build_ydl_opts(self) -> dict:
        ffmpeg_dir = str(self._state.ffmpeg_path.parent) if self._state.ffmpeg_path else ""
        postprocessors = []

        if self._format_mode == "audio":
            fmt = "bestaudio/best"
            # Map codec selection to yt-dlp codec and quality settings
            codec_map = {
                "mp3": ("mp3", "192"),
                "m4a": ("aac", "192"),
                "wav": ("wav", "192"),
                "flac": ("flac", "192"),
                "vorbis": ("vorbis", "192"),
            }
            codec, quality = codec_map.get(self._audio_codec, ("mp3", "192"))
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": quality,
            })
        else:
            # Avoid OPUS audio (not compatible with MP4) — prefer m4a or AAC
            fmt = "bestvideo[ext=mp4]+bestaudio[ext!=webm]/bestvideo+bestaudio/best"
            postprocessors.append({
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            })

        # Add subtitle download if requested
        if self._download_subtitles:
            postprocessors.append({
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt",
            })

        return {
            "format": fmt,
            "outtmpl": str(self._output_dir / "%(title)s.%(ext)s"),
            "ffmpeg_location": ffmpeg_dir,
            "postprocessors": postprocessors,
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": False,
            "logger": self._YtdlpLogger(self.status_update),
            "merge_output_format": "mp4",
            "restrictfilenames": True,
            "writesubtitles": self._download_subtitles,
            "skip_unavailable_fragments": True,
        }

    def _progress_hook(self, d: dict) -> None:
        if self._stop:
            raise yt_dlp.utils.DownloadCancelled()

        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes")
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if downloaded and total:
                pct = int(downloaded / total * 100)
            else:
                try:
                    raw = d.get("_percent_str", "0%").strip().rstrip("%")
                    pct = int(float(raw))
                except (ValueError, AttributeError):
                    pct = 0
            speed = d.get("_speed_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            self.progress_update.emit(pct, speed)
            self.status_update.emit(f"Downloading {pct}%  {speed}  ETA {eta}")

        elif status == "finished":
            filename = Path(d.get("filename", "")).name
            self.progress_update.emit(100, "")
            self.status_update.emit(f"Processing: {filename}")

        elif status == "error":
            self.status_update.emit("Error during download.")

    class _YtdlpLogger:
        def __init__(self, signal):
            self._signal = signal

        def debug(self, msg: str):
            if msg.startswith("[debug]"):
                return
            self._signal.emit(msg)

        def warning(self, msg: str):
            self._signal.emit(f"[warn] {msg}")

        def error(self, msg: str):
            self._signal.emit(f"[error] {msg}")
