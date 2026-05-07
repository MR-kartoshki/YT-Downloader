import os
from pathlib import Path

import yt_dlp
from PySide6.QtCore import QThread, Signal

from core import config


class InfoFetchWorker(QThread):
    duration_fetched = Signal(int)   # duration in seconds
    formats_found = Signal(list)     # list of available heights (ints) in descending order
    fps_found = Signal(list)         # list of available fps (ints) in descending order
    bitrates_found = Signal(list)    # list of available audio bitrates (ints) in descending order
    fetch_failed = Signal(str)

    def __init__(self, url: str, state, parent=None):
        super().__init__(parent)
        self._url = url
        self._state = state

    def run(self):
        try:
            opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self._url, download=False)
            duration = int(info.get("duration") or 0) if info else 0
            heights = self._extract_heights_from_formats(info)
            fps_list = self._extract_fps_from_formats(info)
            bitrates = self._extract_audio_bitrates_from_formats(info)
            if duration > 0:
                self.duration_fetched.emit(duration)
            if heights:
                self.formats_found.emit(heights)
            if fps_list:
                self.fps_found.emit(fps_list)
            if bitrates:
                self.bitrates_found.emit(bitrates)
            if not duration:
                self.fetch_failed.emit("No duration found")
        except Exception as e:
            self.fetch_failed.emit(str(e))

    @staticmethod
    def _extract_heights_from_formats(info):
        heights = set()
        if not info or "formats" not in info:
            return []
        for fmt in info.get("formats", []):
            if fmt.get("vcodec") == "none":
                continue
            h = fmt.get("height")
            if h and h > 0:
                heights.add(h)
        return sorted(heights, reverse=True)

    @staticmethod
    def _extract_fps_from_formats(info):
        fps_vals = set()
        if not info or "formats" not in info:
            return []
        for fmt in info.get("formats", []):
            if fmt.get("vcodec") == "none":
                continue
            fps = fmt.get("fps")
            if fps and fps > 0:
                fps_vals.add(int(fps))
        return sorted(fps_vals, reverse=True)

    @staticmethod
    def _extract_audio_bitrates_from_formats(info):
        bitrates = set()
        if not info or "formats" not in info:
            return []
        for fmt in info.get("formats", []):
            if fmt.get("acodec") == "none":
                continue
            abr = fmt.get("abr")
            if abr and abr > 0:
                bitrates.add(int(abr))
        return sorted(bitrates, reverse=True)


class DownloadWorker(QThread):
    progress_update = Signal(int, str)    # (percent 0-100, speed_string)
    status_update = Signal(str)           # log lines
    download_complete = Signal(bool, str) # (success, message)

    def __init__(self, url: str, output_dir: str, format_mode: str, audio_codec: str,
                 download_subtitles: bool, download_playlist: bool, state,
                 custom_filename: str = "", trim_start: int = None, trim_end: int = None,
                 quality: str = "max", fps: str = "max", audio_bitrate: str = "max",
                 video_container: str = "mp4", parent=None):
        super().__init__(parent)
        self._url = url
        self._output_dir = Path(output_dir)
        self._format_mode = format_mode      # 'video' or 'audio'
        self._video_container = video_container  # 'mp4', 'mkv', 'webm', 'avi', 'mov'
        self._audio_codec = audio_codec      # 'mp3', 'm4a', 'wav', 'flac', 'vorbis'
        self._download_subtitles = download_subtitles
        self._download_playlist = download_playlist
        self._custom_filename = custom_filename
        self._trim_start = trim_start  # seconds or None
        self._trim_end = trim_end      # seconds or None
        self._quality = quality         # 'max' or height like '720'
        self._fps = fps                 # 'max' or fps like '60'
        self._audio_bitrate = audio_bitrate  # 'max' or bitrate like '192'
        self._state = state
        self._stop = False
        self._last_logged_pct = -1

    def cancel(self):
        self._stop = True

    def run(self):
        # Fix 7: download_complete is always emitted, regardless of how run() exits.
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

    def _build_ydl_opts(self) -> dict:
        ffmpeg_dir = str(self._state.ffmpeg_path.parent) if self._state.ffmpeg_path else ""
        postprocessors = []

        if self._format_mode == "audio":
            fmt = "bestaudio/best"
            codec_map = {
                "mp3": "mp3",
                "m4a": "aac",
                "wav": "wav",
                "flac": "flac",
                "vorbis": "vorbis",
            }
            codec = codec_map.get(self._audio_codec, "mp3")
            pp: dict = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
            # Only lossy codecs use a bitrate; WAV/FLAC are lossless and ignore it
            if codec not in ("wav", "flac"):
                pp["preferredquality"] = (
                    self._audio_bitrate if self._audio_bitrate != "max" else "192"
                )
            postprocessors.append(pp)
        else:
            container = self._video_container  # 'mp4', 'mkv', 'webm', 'avi', 'mov'
            quality_constraint = ""
            fps_constraint = ""

            if self._quality != "max":
                h = int(self._quality)
                quality_constraint = f"[height<={h}]"

            if self._fps != "max":
                f = int(self._fps)
                fps_constraint = f"[fps<={f}]"

            qf = quality_constraint + fps_constraint

            if container == "mp4":
                # Prefer native MP4 sources; avoid webm audio (incompatible with MP4)
                fmt = (f"bestvideo[ext=mp4]{qf}+bestaudio[ext!=webm]/"
                       f"bestvideo{qf}+bestaudio/best")
            elif container == "webm":
                # Prefer native WebM sources (VP8/VP9 + Vorbis/Opus)
                fmt = (f"bestvideo[ext=webm]{qf}+bestaudio[ext=webm]/"
                       f"bestvideo{qf}+bestaudio/best")
            else:
                # MKV, AVI, MOV — no codec restrictions, let ffmpeg handle remuxing
                fmt = f"bestvideo{qf}+bestaudio/best"

            postprocessors.append({
                "key": "FFmpegVideoConvertor",
                "preferedformat": container,
            })

        # Add subtitle download if requested
        if self._download_subtitles:
            postprocessors.append({
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt",
            })

        if self._custom_filename:
            # If the user supplied a plain name (no yt-dlp template markers), append the extension
            tmpl = self._custom_filename if "%(" in self._custom_filename else f"{self._custom_filename}.%(ext)s"
        else:
            tmpl = "%(title)s [%(id)s].%(ext)s"

        opts = {
            "format": fmt,
            "outtmpl": str(self._output_dir / tmpl),
            "ffmpeg_location": ffmpeg_dir,
            "postprocessors": postprocessors,
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": False,
            "logger": self._YtdlpLogger(self.status_update),
            "writesubtitles": self._download_subtitles,
            "skip_unavailable_fragments": True,
            "noplaylist": not self._download_playlist,
        }

        if self._format_mode != "audio":
            opts["merge_output_format"] = self._video_container

        if self._trim_start is not None and self._trim_end is not None:
            opts["download_ranges"] = yt_dlp.utils.download_range_func(
                None, [(self._trim_start, self._trim_end)]
            )
            opts["force_keyframes_at_cuts"] = True

        if os.name == "nt":
            opts["windowsfilenames"] = True

        return opts

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
            if pct >= self._last_logged_pct + 2 or pct == 100:
                self._last_logged_pct = pct
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
