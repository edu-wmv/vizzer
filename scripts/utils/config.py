import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class Environment(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


@dataclass
class AppConfig:
    """Application configuration settings."""

    token: str
    request_timeout: int = 10
    max_retries: int = 3

    temp_path: Path = Path("./tmp")
    final_path: Path = Path("./Audio")
    ffmpeg_path: Optional[Path] = Path("/opt/homebrew/bin/ffmpeg")

    cover_size: int = 1000

    log_level: int = logging.INFO

    environment: Environment = Environment.DEVELOPMENT

    @classmethod
    def from_touchdesigner(cls, parent_op) -> "AppConfig":
        """Create config from TouchDesigner parent operator"""

        token = parent_op.par.Usermediatoken.eval()

        if not token:
            raise ValueError("Media User Token not found")

        return cls(token=token)

    def setup_loggin(self) -> None:
        """Configure application-wide logging."""

        logging.basicConfig(
            level=self.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
