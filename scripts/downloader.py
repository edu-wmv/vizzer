import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import requests
from applemusic import AppleMusicAPI
from constants import MP4_TAGS_MAP
from hardcoded_wvd import HARDCODED_WVD
from models import DownloadConfig
from mutagen.mp4 import MP4, MP4Cover
from pywidevine import Cdm, Device
from yt_dlp import YoutubeDL


class DownloadError(Exception):
    """Custom exception for handling download errors."""

    pass


class Downloader:
    """A class to handle audio downloading and metadata tagging."""

    def __init__(self, config: DownloadConfig) -> None:
        """Initialize the Downloader instance."""
        self._validate_config(config)
        self._setup_logging(config.log_level)
        self._initialize_components(config)

    async def __aenter__(self):
        """Async context manager enter."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()

    def _validate_config(self, config: DownloadConfig) -> None:
        """Validate initialization inputs."""
        if not config.token:
            raise ValueError("Token cannot be empty.")

        config.temp_path.mkdir(parents=True, exist_ok=True)
        config.final_path.mkdir(parents=True, exist_ok=True)

        if config.ffmpeg_path and not config.ffmpeg_path.exists():
            raise ValueError(f"ffmpeg not found at {config.ffmpeg_path}")

    def _setup_logging(self, log_level: int) -> None:
        """Configure logging for the Downloader instance."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _initialize_components(self, config: DownloadConfig) -> None:
        """
        Initialize the Downloader components.

        Args:
          config (DownloadConfig): Download configuration settings.

        Raises:
          DownloadError: If initialization fails.
        """

        try:
            self.token = config.token
            self.app = AppleMusicAPI(self.token)
            self.cover_size = config.cover_size

            self._set_cdm()
            self._set_paths(config.temp_path, config.final_path, config.ffmpeg_path)
            self._set_subprocess_args()

            self.exclude_tags = None
            self._set_exclude_tags_list()

            self.logger.info("Components initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing components: {e}")
            raise DownloadError(f"Error initializing components: {e}")

    def _set_cdm(self) -> None:
        """Set the Content Decryption Module (CDM) for Widevine DRM decryption."""
        try:
            self.cdm = Cdm.from_device(Device.loads(HARDCODED_WVD))
            self.logger.debug("CDM initialized successfully")
        except Exception as e:
            self.logger.error(f"CDM initialization failed: {e}")
            raise

    def _set_paths(
        self, temp_path: Path, final_path: Path, ffmpeg_path: Path = None
    ) -> None:
        """Set the paths for utility files and the final audio files."""
        self.temp_path = temp_path
        self.final_path = final_path
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg")

    def _set_subprocess_args(self) -> None:
        """Set the arguments for subprocess calls."""
        self.subprocess_aditional_args = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

    def _set_exclude_tags_list(self) -> None:
        """Set the list of tags to exclude from the metadata."""
        self.exclude_tags_list = (
            [tag.lower() for tag in self.exclude_tags.split(",")]
            if self.exclude_tags
            else []
        )

    def download(self, path: Path, stream_url: str) -> None:
        """Download the audio stream to the specified path."""
        options = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": str(path),
            "allow_unplayable_formats": True,
            "fixup": "never",
            "allowed_extractors": ["generic"],
            "noprogress": False,
        }
        try:
            with YoutubeDL(options) as ydl:
                ydl.download([stream_url])
                self.logger.info(f"Download OK: Successfully downloaded to {path}")
        except Exception as e:
            self.logger.error(f"Download Error: {e}")
            raise DownloadError(f"Failed to download {stream_url}: {str(e)}")

    def getTags(self, webplayback: dict) -> dict:
        """Get the metadata tags from the web playback response."""
        if not webplayback:
            raise ValueError("Webplayback is empty")
        tags_raw = webplayback["assets"][0]["metadata"]
        tags = {
            "album": tags_raw["playlistName"],
            "album_artist": tags_raw["playlistArtistName"],
            "album_id": int(tags_raw["playlistId"]),
            "album_sort": tags_raw["sort-album"],
            "artist": tags_raw["artistName"],
            "artist_id": int(tags_raw["artistId"]),
            "artist_sort": tags_raw["sort-artist"],
            "comments": tags_raw.get("comments"),
            "compilation": tags_raw["compilation"],
            "composer": tags_raw.get("composerName"),
            "composer_id": (
                int(tags_raw.get("composerId")) if tags_raw.get("composerId") else None
            ),
            "composer_sort": tags_raw.get("sort-composer"),
            "copyright": tags_raw.get("copyright"),
            "disc": tags_raw["discNumber"],
            "disc_total": tags_raw["discCount"],
            "gapless": tags_raw["gapless"],
            "genre": tags_raw["genre"],
            "genre_id": tags_raw["genreId"],
            "media_type": 1,
            "rating": tags_raw["explicit"],
            "storefront": tags_raw["s"],
            "title": tags_raw["itemName"],
            "title_id": int(tags_raw["itemId"]),
            "title_sort": tags_raw["sort-name"],
            "track": tags_raw["trackNumber"],
            "track_total": tags_raw["trackCount"],
            "xid": tags_raw.get("xid"),
        }
        self.logger.info("Tags OK: Successfully extracted metadata tags")
        return tags

    def getCoverUrl(self, base_cover: str) -> str:
        """Get the URL of the cover art image."""
        final = re.sub(
            r"\{w\}x\{h\}([a-z]{2})\.jpg",
            f"{self.cover_size}x{self.cover_size}bb.jpg",
            base_cover,
        )
        self.logger.info("Cover URL OK: Successfully extracted cover art URL")
        return final

    def downloadCoverFile(self, cover_url: str) -> str:
        """Download the cover art image to the temporary path."""
        response = requests.get(cover_url, stream=True)
        with open(self.temp_path / "temp_cover.jpg", "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        return str(self.temp_path / "temp_cover.jpg")

    @staticmethod
    def getUrlResponseBytes(url: str) -> bytes:
        """Get the response bytes from a URL."""
        return requests.get(url).content

    def applyTags(self, remux_path: Path, tags: dict, cover_url: str) -> None:
        """Apply the metadata tags to the audio file."""
        to_apply_tags = [
            tag_name
            for tag_name in tags.keys()
            if tag_name not in self.exclude_tags_list
        ]
        mp4_tags = {}
        for tag_name in to_apply_tags:
            if tag_name in ("disc", "disc_total"):
                if mp4_tags.get("disk") is None:
                    mp4_tags["disk"] = [[0, 0]]
                if tag_name == "disc":
                    mp4_tags["disk"][0][0] = tags[tag_name]
                elif tag_name == "disc_total":
                    mp4_tags["disk"][0][1] = tags[tag_name]
            elif tag_name in ("track", "track_total"):
                if mp4_tags.get("trkn") is None:
                    mp4_tags["trkn"] = [[0, 0]]
                if tag_name == "track":
                    mp4_tags["trkn"][0][0] = tags[tag_name]
                elif tag_name == "track_total":
                    mp4_tags["trkn"][0][1] = tags[tag_name]
            elif tag_name == "compilation":
                mp4_tags["cpil"] = tags["compilation"]
            elif tag_name == "gapless":
                mp4_tags["pgap"] = tags["gapless"]
            elif (
                MP4_TAGS_MAP.get(tag_name) is not None
                and tags.get(tag_name) is not None
            ):
                mp4_tags[MP4_TAGS_MAP[tag_name]] = [tags[tag_name]]
        if "cover" not in self.exclude_tags_list:
            mp4_tags["covr"] = [
                MP4Cover(
                    self.getUrlResponseBytes(cover_url),
                    imageformat=MP4Cover.FORMAT_JPEG,
                )
            ]
        mp4 = MP4(remux_path)
        mp4.clear()
        mp4.update(mp4_tags)
        mp4.save()
        self.logger.info("Tags Applied OK: Successfully applied metadata tags")

    def moveToFinalPath(self, remux_path: Path, final_path: Path) -> None:
        """Move the remuxed audio file to the final path."""
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(remux_path, final_path)
        self.logger.info(f"Move OK: Successfully moved to {final_path}")
