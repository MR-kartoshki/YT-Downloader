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
    Returns absolute path to system-root tools directory.
    Works cross-platform (Windows, macOS, Linux).

    - Windows: C:\tools (or D:\tools if on different drive)
    - macOS/Linux: /tools

    Creates the folder if it doesn't exist.
    """
    if sys.platform == "win32":
        # Windows: use system drive (C:\ or D:\, etc.)
        system_drive = Path(os.environ.get("SystemDrive", "C:"))
        tools_dir = system_drive / "tools"
    else:
        # macOS/Linux: use system root
        tools_dir = Path("/tools")

    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir


def get_ffmpeg_path() -> Path:
    return get_tools_dir() / "ffmpeg.exe"


def get_ffprobe_path() -> Path:
    return get_tools_dir() / "ffprobe.exe"


def get_deno_path() -> Path:
    return get_tools_dir() / "deno.exe"


def is_ffmpeg_available() -> bool:
    return get_ffmpeg_path().exists()


def is_deno_available() -> bool:
    return get_deno_path().exists()


def validate_all_tools() -> dict:
    return {
        "ffmpeg": is_ffmpeg_available(),
        "deno": is_deno_available(),
    }
