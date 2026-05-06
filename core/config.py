import sys
from pathlib import Path


def _get_ffmpeg_url() -> str:
    if sys.platform == "win32":
        return "https://github.com/BtbN/ffmpeg-builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    elif sys.platform == "darwin":
        return "https://github.com/BtbN/ffmpeg-builds/releases/download/latest/ffmpeg-master-latest-macos-gpl.zip"
    else:  # linux
        return "https://github.com/BtbN/ffmpeg-builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.zip"


def _get_deno_url() -> str:
    if sys.platform == "win32":
        return "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"
    elif sys.platform == "darwin":
        return "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-apple-darwin.zip"
    else:  # linux
        return "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip"


FFMPEG_URL = _get_ffmpeg_url()
DENO_URL = _get_deno_url()

DEFAULT_OUTPUT_DIR = Path.home() / "Downloads"

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
CHUNK_SIZE = 8192
