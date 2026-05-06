from pathlib import Path

FFMPEG_URL = "https://github.com/BtbN/ffmpeg-builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"

DEFAULT_OUTPUT_DIR = Path.home() / "Downloads"

REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
CHUNK_SIZE = 8192
