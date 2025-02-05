import logging
import shutil
import subprocess
from pathlib import Path

import requests
from mutagen.mp4 import MP4, MP4Cover
from pywidevine import Cdm, Device
from yt_dlp import YoutubeDL

from scripts.api.apple_music import AppleMusicAPI
from scripts.exceptions import DownloadError
from scripts.utils import HARDCODED_WVD
from scripts.utils.config import AppConfig
from scripts.utils.constants import MP4_TAGS_MAP
from scripts.utils.enums import SongCodec
from scripts.utils.helpers import LyrikitHelper


class BaseDownloader:

    def __init__(self, config: AppConfig) -> None:
        """
        Initialize the BasedDownloader instance with configuration.

        Args:
          config (AppConfig): Configuration for the downloader.

        Raises:
          DownloaderError: If initialization fails.
        """

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(config.log_level)

        self._validate_config(config)
        self._initalize_components(config)

    async def __aenter__(self):
        """Async context manager entry method."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Async context manager exit method."""
        await self.cleanup()

    def _validate_config(self, config: AppConfig) -> None:
        """Validate the download configuration."""
        if not config.token:
            raise ValueError("User token cannot be empty.")

        config.temp_path.mkdir(parents=True, exist_ok=True)
        config.final_path.mkdir(parents=True, exist_ok=True)

        if config.ffmpeg_path and not config.ffmpeg_path.exists():
            raise ValueError(f"ffmpeg not founf at {config.ffmpeg_path}")

    def _initalize_components(self, config: AppConfig) -> None:
        """
        Initialize downloader components.

        Args:
          config (AppConfig): Configuration for the downloader.

        Raises:
          DownloaderError: If initialization fails.
        """
        try:
            self.config = config
            self._init_cdm()
            self._set_paths()
            self._set_subprocess_args()

            self.logger.info("Components initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing components: {str(e)}")
            raise DownloadError(f"Error initializing components: {str(e)}")

    def _init_cdm(self) -> None:
        """Initialize the Content Decryption Module."""
        try:
            self.cdm = Cdm.from_device(Device.loads(HARDCODED_WVD))
            self.logger.debug("CDM initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing CDM: {str(e)}")
            raise DownloadError(f"Error initializing CDM: {str(e)}")

    def _set_paths(self) -> None:
        """Set the paths for the downloader."""
        self.temp_path = self.config.temp_path
        self.output_path = self.config.final_path
        self.ffmepg_path = self.config.ffmpeg_path

    def _set_subprocess_args(self) -> None:
        """Set the arguments for the subprocess."""
        self.subprocess_args = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "stdin": subprocess.PIPE,
        }

        if self.ffmepg_path:
            self.subprocess_args["executable"] = str(self.ffmepg_path)

    async def cleanup(self) -> None:
        """Cleanup temporary files."""
        try:
            if self.temp_path.exists():
                # self.logger.info("Cleaning up temporary files.")
                # shutil.rmtree(self.temp_path)
                # self.logger.info("Temporary files removed.")
                pass
        except Exception as e:
            self.logger.error(f"Error cleaning up temporary files: {str(e)}")


class Downloader(BaseDownloader):
    """Main downloader class for handling song downloads."""

    def __init__(self, config: AppConfig, codec: SongCodec = SongCodec.AAC) -> None:
        """
        Initialize the Downloader instance with configuration and codec.

        Args:
          config (AppConfig): Configuration for the downloader.
          codec (SongCodec, optional): Codec for the downloaded song. Defaults to SongCodec.AAC.
        """

        super().__init__(config)
        self.codec = codec
        self.api = AppleMusicAPI(config.token, config.log_level)
        self._set_exclude_tags_list()

    def _set_exclude_tags_list(self) -> None:
        """Set the list of tags to exclude from the metadata."""
        self.exclude_tags = None
        self.exclude_tags_list = (
            [tag.lower() for tag in self.exclude_tags.split(",")]
            if self.exclude_tags
            else []
        )

    def download(self, output_path: Path, url: str) -> None:
        """
        Download content using yt-dlp.

        Args:
          output_path (Path): Path to save the downloaded content.
          url (str): URL of the content to download.

        Raises:
          DownloadError: If download fails.
        """

        ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(output_path),
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with YoutubeDL(ytdl_opts) as ytdl:
                ytdl.download([url])
                self.logger.info(f"Downloaded content to {output_path}")
        except Exception as e:
            self.logger.error(f"Download Error: {str(e)}")
            raise DownloadError(f"Error downloading content from {url}: {str(e)}")

    def get_tags(self, web_playback: dict) -> dict:
        """
        Get tags from the web playback dictionary.

        Args:
          web_playback (dict): Web playback dictionary.

        Returns:
          dict: Tags extracted from the web playback dictionary.
        """
        if not web_playback:
            raise ValueError("Web playback dictionary cannot be empty.")

        tags_raw = web_playback["assets"][0]["metadata"]
        return self._process_tags(tags_raw)

    def apply_tags(self, song_path: Path, tags: dict, cover_url: str) -> None:
        """
        Apply tags and cover art to the downloaded song.

        Args:
          tags (dict): Tags to apply to the song.
          output_path (Path): Path to the downloaded song.
        """
        mp4_tags = self._prepare_mp4_tags(tags)

        if "cover" not in self.exclude_tags_list:
            mp4_tags["covr"] = [self._get_cover_art(cover_url)]

        self._write_tags(song_path, mp4_tags)

    def get_cover_url(self, artwork_url: str) -> str:
        """Format cover art URL with specified size."""
        return artwork_url.format(w=self.config.cover_size, h=self.config.cover_size)

    def _process_tags(self, tags_raw: dict) -> dict:
        """Process the raw tags into structured format."""
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

    def _prepare_mp4_tags(self, tags: dict) -> dict:
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

    def _get_cover_art(self, cover_url: str) -> MP4Cover:
        """Get the cover art from the URL."""
        return MP4Cover(
            LyrikitHelper.getURLResponseBytes(cover_url),
            imageformat=MP4Cover.FORMAT_JPEG,
        )

    def _write_tags(self, song_path: Path, tags: dict) -> None:
        """Write the tags to the song file."""
        mp4 = MP4(song_path)
        mp4.clear()
        mp4.update(tags)
        mp4.save()
        self.logger.info("Tags applied successfully.")
