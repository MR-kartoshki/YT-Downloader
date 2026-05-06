import shutil
import zipfile
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
            # Get absolute path to system-root tools folder
            # Windows: C:\tools, macOS/Linux: /tools
            tools_dir = get_tools_dir()

            # --- ffmpeg (required) ---
            # First check if ffmpeg is in system PATH
            ffmpeg_in_path = shutil.which("ffmpeg")
            if ffmpeg_in_path:
                self._state.ffmpeg_ready = True
                self._state.ffmpeg_path = Path(ffmpeg_in_path)
                self.tool_status_changed.emit("ffmpeg", "Ready")
                self.log_message.emit(f"ffmpeg found in PATH: {ffmpeg_in_path}")
            elif not is_ffmpeg_available():
                ok = self._fetch_tool("ffmpeg", config.FFMPEG_URL, tools_dir)
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
            else:
                if self._validate_binary(get_ffmpeg_path(), _MIN_FFMPEG_SIZE, "ffmpeg"):
                    self._state.ffmpeg_ready = True
                    self._state.ffmpeg_path = get_ffmpeg_path()
                    self.tool_status_changed.emit("ffmpeg", "Ready")
                    self.log_message.emit("ffmpeg already present.")
                else:
                    # Existing file is corrupt — re-download
                    self.log_message.emit("ffmpeg.exe is corrupt, re-downloading...")
                    get_ffmpeg_path().unlink(missing_ok=True)
                    ok = self._fetch_tool("ffmpeg", config.FFMPEG_URL, tools_dir)
                    if ok and self._validate_binary(get_ffmpeg_path(), _MIN_FFMPEG_SIZE, "ffmpeg"):
                        self._state.ffmpeg_ready = True
                        self._state.ffmpeg_path = get_ffmpeg_path()
                        self.tool_status_changed.emit("ffmpeg", "Ready")
                    else:
                        self.tool_status_changed.emit("ffmpeg", "Failed")

            # --- deno ---
            # First check if deno is in system PATH
            deno_in_path = shutil.which("deno")
            if deno_in_path:
                self._state.deno_ready = True
                self._state.deno_path = Path(deno_in_path)
                self.tool_status_changed.emit("deno", "Ready")
                self.log_message.emit(f"deno found in PATH: {deno_in_path}")
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
            else:
                if self._validate_binary(get_deno_path(), _MIN_DENO_SIZE, "deno"):
                    self._state.deno_ready = True
                    self._state.deno_path = get_deno_path()
                    self.tool_status_changed.emit("deno", "Ready")
                    self.log_message.emit("deno already present.")
                else:
                    self.log_message.emit("deno.exe is corrupt, re-downloading...")
                    get_deno_path().unlink(missing_ok=True)
                    ok = self._fetch_tool("deno", config.DENO_URL, tools_dir)
                    if ok and self._validate_binary(get_deno_path(), _MIN_DENO_SIZE, "deno"):
                        self._state.deno_ready = True
                        self._state.deno_path = get_deno_path()
                        self.tool_status_changed.emit("deno", "Ready")
                    else:
                        self.tool_status_changed.emit("deno", "Failed")

            # tools_ready only requires ffmpeg (see state.py)
            self.bootstrap_complete.emit(self._state.tools_ready, "")

        except Exception as e:
            self.log_message.emit(f"Bootstrap error: {e}")
            self.bootstrap_complete.emit(False, str(e))

    # ------------------------------------------------------------------ #
    # High-level fetch helper
    # ------------------------------------------------------------------ #

    def _fetch_tool(self, tool_name: str, url: str, tools_dir: Path) -> bool:
        """Download zip, validate it, extract binary. Returns True on success."""
        zip_path = tools_dir / f"{tool_name}_download.zip"
        self.tool_status_changed.emit(tool_name, "Downloading...")

        ok = self._download_zip(url, zip_path, tool_name)
        if not ok:
            return False

        self.tool_status_changed.emit(tool_name, "Extracting...")
        if tool_name == "ffmpeg":
            ok = self._extract_ffmpeg(zip_path, tools_dir)
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
        Fix 2: extract both ffmpeg.exe AND ffprobe.exe — both are required.
        Does not assume any fixed folder structure in the zip.
        """
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                for target_name in ("ffmpeg.exe", "ffprobe.exe"):
                    lower = target_name.lower()
                    match = next(
                        (n for n in names if n.lower().endswith(f"/{lower}")),
                        None,
                    )
                    if match is None:
                        match = next(
                            (n for n in names if n.lower() == lower),
                            None,
                        )
                    if match:
                        dest = dest_dir / target_name
                        with zf.open(match) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        self.log_message.emit(f"Extracted {target_name}.")
                    else:
                        # Both binaries are required
                        self.log_message.emit(
                            f"Could not find {target_name} in zip — extraction failed."
                        )
                        return False
            return True
        except Exception as e:
            self.log_message.emit(f"ffmpeg extraction error: {e}")
            return False

    def _extract_deno(self, zip_path: Path, dest_dir: Path) -> bool:
        """Extract deno.exe from zip. Tries multiple patterns."""
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()

                # Debug: log what's in the zip
                exe_files = [n for n in names if n.lower().endswith(".exe")]
                if exe_files:
                    self.log_message.emit(f"Found .exe files in zip: {exe_files[:3]}")

                # Priority 1: exact match for deno.exe
                match = next(
                    (n for n in names if n.lower() == "deno.exe"),
                    None,
                )

                # Priority 2: any file named deno.exe (case-insensitive)
                if match is None:
                    match = next(
                        (n for n in names if n.lower().endswith("/deno.exe") or
                         n.lower().endswith("\\deno.exe")),
                        None,
                    )

                # Priority 3: any .exe containing "deno"
                if match is None:
                    match = next(
                        (n for n in names if "deno" in n.lower() and n.lower().endswith(".exe")),
                        None,
                    )

                # Priority 4: any .exe (fallback)
                if match is None:
                    match = next((n for n in names if n.lower().endswith(".exe")), None)

                if match is None:
                    self.log_message.emit(f"Could not find deno.exe in zip. Contents: {names[:10]}")
                    return False

                dest = dest_dir / "deno.exe"
                with zf.open(match) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                self.log_message.emit(f"Extracted deno.exe from {match}.")
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
