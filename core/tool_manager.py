import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_tools_dir() -> Path:
    tools = get_app_base_dir() / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    return tools


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
