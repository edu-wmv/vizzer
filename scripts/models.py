import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class StreamInfo:
    stream_url: str = None
    pssh: str = None
    codec: str = None


@dataclass
class URLInfo:
    """Data class to store URL parsing results"""

    track_id: str
    kind: str
    is_valid: bool = False


@dataclass
class LyricLine:
    """Data class for storing lyric line information."""

    text: str
    begin_time: Optional[str] = None
    end_time: Optional[str] = None
    begin_time_ms: Optional[float] = None
    end_time_ms: Optional[float] = None


@dataclass
class DownloadConfig:
    """Configuration for downloading a song."""

    token: str
    cover_size: int = 1000
    temp_path: Path = Path("/tmp")
    final_path: Path = Path("/Audio")
    ffmpeg_path: Optional[Path] = Path("/opt/homebrew/bin/ffmpeg")
    log_level: int = logging.INFO
    max_retries: int = 3
    timeout: int = 10
