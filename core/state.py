from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AppState:
    ffmpeg_ready: bool = False
    deno_ready: bool = False
    ffmpeg_path: Optional[Path] = None
    deno_path: Optional[Path] = None
    download_active: bool = False

    @property
    def tools_ready(self) -> bool:
        return self.ffmpeg_ready and self.deno_ready
