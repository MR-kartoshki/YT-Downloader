import shutil
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from core import config
from core.tool_manager import (
    get_tools_dir,
    get_ffmpeg_path,
    get_ffprobe_path,
    get_deno_path,
    is_ffmpeg_available,
    is_deno_available,
)

# Minimum expected binary sizes (bytes). Anything smaller is corrupt/partial.
_MIN_FFMPEG_SIZE = 1_000_000    # ~1 MB minimum
_MIN_DENO_SIZE = 1_000_000      # ~1 MB minimum


class BootstrapWorker(QThread):
    tool_status_changed = Signal(str, str)   # (tool_name, status_message)
    tool_progress = Signal(str, int)         # (tool_name, 0-100)
    bootstrap_complete = Signal(bool, str)   # (success, error_or_empty)
    log_message = Signal(str)

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    def run(self):
        try:
            tools_dir = get_tools_dir()
            with ThreadPoolExecutor(max_workers=2) as executor:
                f_ffmpeg = executor.submit(self._setup_ffmpeg, tools_dir)
                f_deno   = executor.submit(self._setup_deno,   tools_dir)
                f_ffmpeg.result()
                f_deno.result()
            self.bootstrap_complete.emit(self._state.tools_ready, "")
        except Exception as e:
            self.log_message.emit(f"Bootstrap error: {e}")
            self.bootstrap_complete.emit(False, str(e))

    def _setup_ffmpeg(self, tools_dir: Path) -> bool:
        ffmpeg_in_path = shutil.which("ffmpeg")
        if ffmpeg_in_path:
            self._state.ffmpeg_ready = True
            self._state.ffmpeg_path = Path(ffmpeg_in_path)
            self.tool_status_changed.emit("ffmpeg", "Ready")
            self.log_message.emit(f"ffmpeg found in PATH: {ffmpeg_in_path}")
            return True
        elif not is_ffmpeg_available():
            ok = self._fetch_tool("ffmpeg", config.FFMPEG_URL, tools_dir)
            if ok and config.FFPROBE_URL:
                if not self._fetch_tool("ffprobe", config.FFPROBE_URL, tools_dir):
                    self.log_message.emit("ffprobe download failed — some features may be limited.")
            if ok:
                ok = self._validate_binary(get_ffmpeg_path(), _MIN_FFMPEG_SIZE, "ffmpeg")
            if ok:
                self._state.ffmpeg_ready = True
                self._state.ffmpeg_path = get_ffmpeg_path()
                self.tool_status_changed.emit("ffmpeg", "Ready")
                self.log_message.emit("ffmpeg ready.")
            else:
                self.tool_status_changed.emit("ffmpeg", "Failed")
                self.log_message.emit("ffmpeg setup failed.")
            return ok
        else:
            if self._validate_binary(get_ffmpeg_path(), _MIN_FFMPEG_SIZE, "ffmpeg"):
                self._state.ffmpeg_ready = True
                self._state.ffmpeg_path = get_ffmpeg_path()
                self.tool_status_changed.emit("ffmpeg", "Ready")
                self.log_message.emit("ffmpeg already present.")
                return True
            else:
                ffmpeg_name = get_ffmpeg_path().name
                self.log_message.emit(f"{ffmpeg_name} is corrupt, re-downloading...")
                get_ffmpeg_path().unlink(missing_ok=True)
                ok = self._fetch_tool("ffmpeg", config.FFMPEG_URL, tools_dir)
                if ok and config.FFPROBE_URL:
                    if not self._fetch_tool("ffprobe", config.FFPROBE_URL, tools_dir):
                        self.log_message.emit("ffprobe download failed — some features may be limited.")
                if ok and self._validate_binary(get_ffmpeg_path(), _MIN_FFMPEG_SIZE, "ffmpeg"):
                    self._state.ffmpeg_ready = True
                    self._state.ffmpeg_path = get_ffmpeg_path()
                    self.tool_status_changed.emit("ffmpeg", "Ready")
                else:
                    self.tool_status_changed.emit("ffmpeg", "Failed")
                return ok

    def _setup_deno(self, tools_dir: Path) -> bool:
        deno_in_path = shutil.which("deno")
        if deno_in_path:
            self._state.deno_ready = True
            self._state.deno_path = Path(deno_in_path)
            self.tool_status_changed.emit("deno", "Ready")
            self.log_message.emit(f"deno found in PATH: {deno_in_path}")
            return True
        elif not is_deno_available():
            ok = self._fetch_tool("deno", config.DENO_URL, tools_dir)
            if ok:
                ok = self._validate_binary(get_deno_path(), _MIN_DENO_SIZE, "deno")
            if ok:
                self._state.deno_ready = True
                self._state.deno_path = get_deno_path()
                self.tool_status_changed.emit("deno", "Ready")
                self.log_message.emit("deno ready.")
            else:
                self.tool_status_changed.emit("deno", "Failed")
                self.log_message.emit("deno setup failed.")
            return ok
        else:
            if self._validate_binary(get_deno_path(), _MIN_DENO_SIZE, "deno"):
                self._state.deno_ready = True
                self._state.deno_path = get_deno_path()
                self.tool_status_changed.emit("deno", "Ready")
                self.log_message.emit("deno already present.")
                return True
            else:
                deno_name = get_deno_path().name
                self.log_message.emit(f"{deno_name} is corrupt, re-downloading...")
                get_deno_path().unlink(missing_ok=True)
                ok = self._fetch_tool("deno", config.DENO_URL, tools_dir)
                if ok and self._validate_binary(get_deno_path(), _MIN_DENO_SIZE, "deno"):
                    self._state.deno_ready = True
                    self._state.deno_path = get_deno_path()
                    self.tool_status_changed.emit("deno", "Ready")
                else:
                    self.tool_status_changed.emit("deno", "Failed")
                return ok

    # ------------------------------------------------------------------ #
    # High-level fetch helper
    # ------------------------------------------------------------------ #

    def _fetch_tool(self, tool_name: str, url: str, tools_dir: Path) -> bool:
        """Download zip, validate it, extract binary. Returns True on success."""
        # Create tools directory only when actually downloading
        tools_dir.mkdir(parents=True, exist_ok=True)
        zip_path = tools_dir / f"{tool_name}_download.zip"
        self.tool_status_changed.emit(tool_name, "Downloading...")

        ok = self._download_zip(url, zip_path, tool_name)
        if not ok:
            return False

        self.tool_status_changed.emit(tool_name, "Extracting...")
        if tool_name == "ffmpeg":
            ok = self._extract_ffmpeg(zip_path, tools_dir)
        elif tool_name == "ffprobe":
            ok = self._extract_single_binary(zip_path, tools_dir, "ffprobe")
        else:
            ok = self._extract_deno(zip_path, tools_dir)

        self._cleanup_zip(zip_path)
        return ok

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #

    def _download_zip(self, url: str, dest_zip: Path, tool_name: str) -> bool:
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                self.log_message.emit(f"[{tool_name}] Connecting (attempt {attempt})...")
                response = requests.get(
                    url, stream=True, timeout=config.REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
                response.raise_for_status()

                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                with open(dest_zip, "wb") as f:
                    for chunk in response.iter_content(chunk_size=config.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                pct = int(downloaded / total * 100)
                                self.tool_progress.emit(tool_name, pct)

                # Fix 1: validate zip magic bytes (PK signature)
                if not self._is_valid_zip(dest_zip):
                    self.log_message.emit(
                        f"[{tool_name}] Response is not a valid zip "
                        f"(got HTML or error page?). Retrying..."
                    )
                    dest_zip.unlink(missing_ok=True)
                    continue

                self.tool_progress.emit(tool_name, 100)
                self.log_message.emit(f"[{tool_name}] Download complete.")
                return True

            except Exception as e:
                self.log_message.emit(f"[{tool_name}] Attempt {attempt} failed: {e}")
                dest_zip.unlink(missing_ok=True)

        return False

    # ------------------------------------------------------------------ #
    # Extraction
    # ------------------------------------------------------------------ #

    def _extract_ffmpeg(self, zip_path: Path, dest_dir: Path) -> bool:
        """
        Extract ffmpeg (and ffprobe where bundled) from zip.
        On macOS, ffprobe is downloaded separately so its absence here is not an error.
        """
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()

                is_windows = sys.platform == "win32"
                # macOS gets ffprobe from a separate archive (config.FFPROBE_URL)
                ffprobe_required = sys.platform != "darwin"
                target_binaries = [
                    ("ffmpeg.exe" if is_windows else "ffmpeg", "ffmpeg", True),
                    ("ffprobe.exe" if is_windows else "ffprobe", "ffprobe", ffprobe_required),
                ]

                for target_name, base_name, required in target_binaries:
                    match = next(
                        (n for n in names if n.lower() == target_name.lower()), None
                    )
                    if match is None:
                        match = next(
                            (n for n in names if n.lower().endswith(f"/{target_name.lower()}") or
                             n.lower().endswith(f"\\{target_name.lower()}")),
                            None,
                        )
                    if match is None:
                        match = next(
                            (n for n in names if base_name.lower() in n.lower() and
                             not n.lower().endswith(".txt") and not n.lower().endswith(".md")),
                            None,
                        )

                    if match:
                        dest = dest_dir / target_name
                        with zf.open(match) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        if not is_windows:
                            dest.chmod(0o755)
                        self.log_message.emit(f"Extracted {target_name}.")
                    elif required:
                        self.log_message.emit(
                            f"Could not find {target_name} in zip — extraction failed."
                        )
                        return False
            return True
        except Exception as e:
            self.log_message.emit(f"ffmpeg extraction error: {e}")
            return False

    def _extract_single_binary(self, zip_path: Path, dest_dir: Path, name: str) -> bool:
        """Extract a single named binary from a zip (used for macOS ffprobe)."""
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                is_windows = sys.platform == "win32"
                target_name = f"{name}.exe" if is_windows else name

                match = next((n for n in names if n.lower() == target_name.lower()), None)
                if match is None:
                    match = next(
                        (n for n in names if n.lower().endswith(f"/{target_name.lower()}") or
                         n.lower().endswith(f"\\{target_name.lower()}")),
                        None,
                    )
                if match is None:
                    match = next(
                        (n for n in names if name.lower() in n.lower() and
                         not n.lower().endswith(".txt") and not n.lower().endswith(".md")),
                        None,
                    )

                if match is None:
                    self.log_message.emit(f"Could not find {target_name} in zip.")
                    return False

                dest = dest_dir / target_name
                with zf.open(match) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                if not is_windows:
                    dest.chmod(0o755)
                self.log_message.emit(f"Extracted {target_name}.")
            return True
        except Exception as e:
            self.log_message.emit(f"{name} extraction error: {e}")
            return False

    def _extract_deno(self, zip_path: Path, dest_dir: Path) -> bool:
        """Extract deno binary from zip. Handles Windows (.exe) and Unix formats."""
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()

                is_windows = sys.platform == "win32"
                target_name = "deno.exe" if is_windows else "deno"

                # Priority 1: exact case-insensitive match
                match = next(
                    (n for n in names if n.lower() == target_name.lower()),
                    None,
                )

                # Priority 2: ends with /binary or \binary (nested in folder)
                if match is None:
                    match = next(
                        (n for n in names if n.lower().endswith(f"/{target_name.lower()}") or
                         n.lower().endswith(f"\\{target_name.lower()}")),
                        None,
                    )

                # Priority 3: contains "deno" and looks executable
                if match is None:
                    # On Windows, look for .exe; on Unix, look for anything with deno
                    if is_windows:
                        match = next(
                            (n for n in names if "deno" in n.lower() and n.lower().endswith(".exe")),
                            None,
                        )
                    else:
                        match = next(
                            (n for n in names if "deno" in n.lower() and
                             not n.lower().endswith(".txt") and not n.lower().endswith(".md")),
                            None,
                        )

                # Priority 4: Windows-only fallback to any .exe
                if match is None and is_windows:
                    match = next((n for n in names if n.lower().endswith(".exe")), None)

                if match is None:
                    self.log_message.emit(f"Could not find deno binary in zip. Contents: {names[:10]}")
                    return False

                dest = dest_dir / target_name
                with zf.open(match) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                # Make executable on Unix
                if not is_windows:
                    dest.chmod(0o755)
                self.log_message.emit(f"Extracted {target_name} from {match}.")
            return True
        except Exception as e:
            self.log_message.emit(f"deno extraction error: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def _is_valid_zip(self, path: Path) -> bool:
        """Check PK magic bytes. If invalid, log first 200 bytes for debugging."""
        try:
            with open(path, "rb") as f:
                header = f.read(2)
                if header != b"PK":
                    # Log first part of file to detect error pages, HTML, etc.
                    f.seek(0)
                    content_sample = f.read(200)
                    try:
                        text_sample = content_sample.decode("utf-8", errors="ignore")[:100]
                        if "<!DOCTYPE" in text_sample or "<html" in text_sample:
                            self.log_message.emit(
                                "Downloaded file is HTML (not zip) — GitHub may be rate-limiting or URL is wrong."
                            )
                        else:
                            self.log_message.emit(f"Not a zip file. Header: {content_sample[:50]}")
                    except Exception:
                        pass
                    return False
                return True
        except Exception:
            return False

    def _validate_binary(self, path: Path, min_bytes: int, name: str) -> bool:
        """Fix 8: reject binaries smaller than min_bytes (corrupt/partial download)."""
        if not path.exists():
            return False
        size = path.stat().st_size
        if size < min_bytes:
            self.log_message.emit(
                f"{name} binary is only {size} bytes — too small, likely corrupt."
            )
            return False
        return True

    # ------------------------------------------------------------------ #

    def _cleanup_zip(self, zip_path: Path) -> None:
        try:
            if zip_path.exists():
                zip_path.unlink()
        except Exception:
            pass
