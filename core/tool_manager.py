import os
import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    """
    Returns the absolute path to the app directory (where main.py or exe is located).
    Used for finding bundled files like the icon.
    Works cross-platform (Windows, macOS, Linux).

    - Frozen (PyInstaller .exe): directory containing the executable
    - Development: project root directory (parent of core/)
    """
    if getattr(sys, "frozen", False):
        # Running as compiled .exe from PyInstaller
        return Path(sys.executable).resolve().parent
    else:
        # Running as Python script: parent of core/ directory
        return Path(__file__).resolve().parent.parent


def get_tools_dir() -> Path:
    """
    Returns absolute path to tools directory.
    Works cross-platform (Windows, macOS, Linux).

    - Windows: C:\tools (or D:\tools if on different drive)
    - macOS/Linux: ~/.yt-downloader/tools (user home directory)

    Does NOT create the folder — only returns the path.
    """
    if sys.platform == "win32":
        # Windows: use system drive (C:\ or D:\, etc.)
        system_drive = Path(os.environ.get("SystemDrive", "C:"))
        tools_dir = system_drive / "tools"
    else:
        # macOS/Linux: use user home directory (writable by regular users)
        home = Path.home()
        tools_dir = home / ".yt-downloader" / "tools"

    return tools_dir


def get_ffmpeg_path() -> Path:
    # Windows: ffmpeg.exe, Linux/macOS: ffmpeg
    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    return get_tools_dir() / exe_name


def get_ffprobe_path() -> Path:
    # Windows: ffprobe.exe, Linux/macOS: ffprobe
    exe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    return get_tools_dir() / exe_name


def get_deno_path() -> Path:
    # Windows: deno.exe, Linux/macOS: deno
    exe_name = "deno.exe" if sys.platform == "win32" else "deno"
    return get_tools_dir() / exe_name


def is_ffmpeg_available() -> bool:
    return get_ffmpeg_path().exists()


def is_deno_available() -> bool:
    return get_deno_path().exists()


def validate_all_tools() -> dict:
    return {
        "ffmpeg": is_ffmpeg_available(),
        "deno": is_deno_available(),
    }


def patch_tools_path() -> None:
    """Prepend tools_dir to PATH once. Idempotent — safe to call multiple times."""
    tools_dir = str(get_tools_dir())
    sep = ";" if os.name == "nt" else ":"
    current = os.environ.get("PATH", "")
    entries = current.split(sep)
    if sys.platform == "win32":
        already_present = any(
            e.strip().lower().rstrip("\\/") == tools_dir.lower().rstrip("\\/")
            for e in entries
        )
    else:
        already_present = tools_dir in entries
    if not already_present:
        os.environ["PATH"] = f"{tools_dir}{sep}{current}"
