import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from core.version import __version__
from core.tool_manager import get_app_base_dir

# Fetch version info from the latest release (no auth needed, public)
VERSION_INFO_URL = "https://github.com/MR-kartoshki/YT-Downloader/releases/latest/download/version.json"

_ASSET_NAMES = {
    "win32":  "ytdownloader.exe",
    "linux":  "ytdownloader",
    "darwin": "ytdownloader-macos.zip",
}

IS_FROZEN = getattr(sys, "frozen", False)

_CACHE_TTL = 86400  # 1 day in seconds
_CACHE_FILE = get_app_base_dir() / ".update_cache.json"


def _get_cache() -> dict | None:
    """Load cached check result if fresh (< 24 hours old)."""
    if not _CACHE_FILE.exists():
        return None
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        age = time.time() - data.get("timestamp", 0)
        if age < _CACHE_TTL:
            return data
    except Exception:
        pass
    return None


def _set_cache(data: dict) -> None:
    """Save check result with timestamp."""
    data["timestamp"] = time.time()
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split("."))


class UpdateCheckWorker(QThread):
    update_available = Signal(str, str)  # (latest_version, download_url)
    up_to_date = Signal(str)             # (latest_version,)
    check_failed = Signal(str)

    def run(self):
        try:
            # Try cache first
            cache = _get_cache()
            if cache:
                self._emit_from_cache(cache)
                return

            # Cache miss or stale — fetch version.json from latest release
            resp = requests.get(VERSION_INFO_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            latest = data["version"]

            if _parse_version(latest) > _parse_version(__version__):
                asset_name = _ASSET_NAMES.get(sys.platform)
                if not asset_name:
                    self.check_failed.emit(f"Unsupported platform: {sys.platform}")
                    return
                url = next(
                    (a["url"] for a in data.get("assets", [])
                     if a["name"] == asset_name),
                    None,
                )
                if url:
                    _set_cache({"status": "available", "version": latest, "url": url})
                    self.update_available.emit(latest, url)
                else:
                    self.check_failed.emit(f"No release asset found for {sys.platform}")
            else:
                _set_cache({"status": "up_to_date", "version": latest})
                self.up_to_date.emit(latest)
        except Exception as e:
            self.check_failed.emit(str(e))

    def _emit_from_cache(self, cache: dict) -> None:
        status = cache.get("status")
        version = cache.get("version")
        if status == "available":
            url = cache.get("url")
            if url:
                self.update_available.emit(version, url)
        elif status == "up_to_date":
            self.up_to_date.emit(version)


class UpdateDownloadWorker(QThread):
    progress = Signal(int)   # 0-100
    finished = Signal(str)   # absolute path to downloaded temp file
    failed = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            resp = requests.get(self._url, stream=True, timeout=60, allow_redirects=True)
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            suffix = Path(self._url).suffix or ".tmp"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix)
            downloaded = 0
            with os.fdopen(fd, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded / total * 100))
            self.progress.emit(100)
            self.finished.emit(tmp_path)
        except Exception as e:
            self.failed.emit(str(e))


def apply_update(tmp_path: str) -> None:
    """
    Replace the running executable with the downloaded file, then restart.
    Must be called from the main thread right before the process exits.
    """
    current_exe = Path(sys.executable)

    # macOS ships a .zip — extract the binary from it first
    if sys.platform == "darwin" and tmp_path.endswith(".zip"):
        tmp_path = _extract_macos_binary(tmp_path)
        if tmp_path is None:
            raise RuntimeError("Could not extract binary from macOS zip.")

    if sys.platform == "win32":
        _apply_windows(tmp_path, current_exe)
    else:
        _apply_unix(tmp_path, current_exe)


def _extract_macos_binary(zip_path: str) -> str | None:
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        binary = next(
            (n for n in names if "ytdownloader" in n.lower() and not n.endswith("/")),
            names[0] if names else None,
        )
        if binary is None:
            return None
        fd, out_path = tempfile.mkstemp()
        with zf.open(binary) as src, os.fdopen(fd, "wb") as dst:
            dst.write(src.read())
    os.unlink(zip_path)
    return out_path


def _apply_windows(tmp_path: str, current_exe: Path) -> None:
    import subprocess
    fd, bat_path = tempfile.mkstemp(suffix=".bat")
    bat = (
        "@echo off\n"
        "timeout /t 2 /nobreak >nul\n"
        f'move /Y "{tmp_path}" "{current_exe}"\n'
        f'start "" "{current_exe}"\n'
        'del "%~f0"\n'
    )
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(bat)
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    sys.exit(0)


def _apply_unix(tmp_path: str, current_exe: Path) -> None:
    os.chmod(tmp_path, 0o755)
    os.replace(tmp_path, str(current_exe))
    os.execv(str(current_exe), sys.argv)
