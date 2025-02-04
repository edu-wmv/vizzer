import base64
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import m3u8
from downloader import Downloader
from enums import SongCodec
from models import DownloadConfig, StreamInfo
from pywidevine import PSSH
from pywidevine.license_protocol_pb2 import WidevinePsshData


class LegacyDownloadError(Exception):
    pass


class StreamInfoError(Exception):
    pass


class DownloaderSongLegacy:
    """
    Legacy song downloader implementation for handling specific codec formats.

    This class manages the download of audio streams using legacy codecs,
    specifically AAC-HE-Legacy and AAC-Legacy.

    Attributes:
      codec (SongCodec): Audio codec used to download the song.
      token (str): User token for Apple Music API authentication.
      logger (logging.Logger): Logger instance for the class.
    """

    def __init__(
        self, codec: SongCodec, token: str, log_level: int = logging.INFO
    ) -> None:
        """
        Initialize the Legacy Downloader instance.

        Args:
          codec (SongCodec): Audio codec used to download the song.
          token (str): User token for Apple Music API authentication.
          log_level (int, optional): Log level for the logger instance. Defaults to logging.INFO.

        Raises:
          ValueError: If the token is empty or codec is invalid
        """

        self._validate_inputs(codec, token)
        self._setup_logging(log_level)

        self.codec = codec
        self.token = token
        config = DownloadConfig(
            token=token,
            temp_path=Path("./tmp"),
            final_path=Path("./Audio"),
            cover_size=1000,
            log_level=log_level,
        )
        self.downloader = Downloader(config)

    def _validate_inputs(self, codec, token: str) -> None:
        """Validate initialization params"""

        if not token:
            raise ValueError("Token cannot be empty.")
        if not isinstance(codec, SongCodec):
            raise ValueError(f"Invalid codec type: {type(codec)}")

    def _setup_logging(self, log_level: int) -> None:
        """Configure logging for the Legacy Downloader instance."""

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _get_flavor_for_codec(self) -> str:
        """Get the apropriate flavor string for the current codec"""
        return "32:ctrp64" if self.codec == SongCodec.AAC_HE_LEGACY else "28:ctrp256"

    def _extract_stream_url(
        self, webplayback: Dict[str, Any], flavor: str
    ) -> Optional[str]:
        """Extract the stream URL from the webplayback data"""
        try:
            return next(
                x["URL"] for x in webplayback["assets"] if x["flavor"] == flavor
            )
        except StopIteration:
            return None

    async def _load_m3u8(self, url: str) -> m3u8.M3U8:
        """Load the M3U8 playlist from the given URL"""
        try:
            return m3u8.load(uri=url, verify_ssl=False)
        except Exception as e:
            self.logger.error(f"Error loading m3u8 file: {e}")
            raise LegacyDownloadError(f"Error loading m3u8 file: {e}")

    async def get_stream_info(self, webplayback: Dict[str, Any]) -> StreamInfo:
        """
        Retrieve the stream info for the song from the webplayback data.

        Args:
          webplayback (Dict[str, Any]): Webplayback data for the song.

        Returns:
          StreamInfo: Object containing the stream URL, PSSH data, and codec.

        Raises:
          StreamInfoError: If stream info cannot be retrieved.
          ValueError: If the webplayback data is invalid.
        """

        if not webplayback or "assets" not in webplayback:
            raise ValueError("Invalid webplayback data")

        try:
            flavor = self._get_flavor_for_codec()
            stream_info = StreamInfo()

            stream_url = self._extract_stream_url(webplayback, flavor)
            if not stream_url:
                raise StreamInfoError("Stream URL not found")
            stream_info.stream_url = stream_url

            m3u8_obj = await self._load_m3u8(stream_info.stream_url)
            if not m3u8_obj.keys:
                raise StreamInfoError("PSSH data not found")

            stream_info.pssh = m3u8_obj.keys[0].uri
            stream_info.codec = self.codec

            self.logger.info("Stream info retrieved successfully")
            return stream_info

        except Exception as e:
            self.logger.error(f"Error getting stream info: {e}")
            raise StreamInfoError(f"Error getting stream info: {e}")

    async def get_decryption_key(self, pssh: str, track_id: str) -> str:
        """
        Get the decryption key for the song using the Widevine license.

        Args:
          pssh (str): PSSH data for the song.
          track_id (str): Track ID for the song.

        Returns:
          str: Decryption key in hexadecimal format for the song.

        Raises:
          LegacyDownloadError: If the decryption key cannot be retrieved.
        """

        try:
            self.logger.debug(f"Getting decryption key for track {track_id}")

            wdv_pssh_data = WidevinePsshData()
            wdv_pssh_data.algorithm = 1
            wdv_pssh_data.key_ids.append(base64.b64decode(pssh.split(",")[1]))
            pssh_obj = PSSH(wdv_pssh_data.SerializeToString())

            cdm_session = self.downloader.cdm.open()
            challenge = base64.b64encode(
                self.downloader.cdm.get_license_challenge(cdm_session, pssh_obj)
            ).decode()

            license = self.downloader.app.get_widevine_license(
                track_id, pssh, challenge
            )
            self.downloader.cdm.parse_license(cdm_session, license)

            decryption_key = next(
                x
                for x in self.downloader.cdm.get_keys(cdm_session)
                if x.type == "CONTENT"
            ).key.hex()

            self.logger.info("Decryption key retrieved successfully")
            return decryption_key

        except Exception as e:
            self.logger.error(f"Error getting decryption key: {e}")
            raise LegacyDownloadError(f"Error getting decryption key: {e}")
        finally:
            if "cdm_session" in locals():
                self.downloader.cdm.close(cdm_session)

    def get_encrypted_path(self, track_id: str) -> Path:
        """
        Get the path for the encrypted song file.

        Args:
          track_id (str): Track ID for the song.

        Returns:
          Path: Path to the encrypted song file.
        """
        if not track_id:
            raise ValueError("Track ID cannot be empty")
        return self.downloader.temp_path / f"{track_id}_encrypted.m4a"

    def get_remuxed_path(self, track_id: str) -> Path:
        """
        Get the path for the remuxed song file.

        Args:
          track_id (str): Track ID for the song.

        Returns:
          Path: Path to the remuxed song file.
        """
        if not track_id:
            raise ValueError("Track ID cannot be empty")
        return self.downloader.temp_path / f"{track_id}_remuxed.m4a"

    def get_final_path(self) -> Path:
        """
        Get the path for the final song file.

        Returns:
          Path: Path to the final song file.
        """
        final_path = self.downloader.final_path / "song.m4a"
        self.logger.debug(f"Final path set to: {final_path}")
        return final_path

    def remux(
        self, encrypted_path: Path, remuxed_path: Path, decryption_key: str
    ) -> None:
        """
        Remux the encrypted song file to the final song file using the decryption key.

        Args:
          encrypted_path (Path): Path to the encrypted song file.
          remuxed_path (Path): Path to the remuxed song file.
          decryption_key (str): Decryption key for the song.

        Raises:
          subprocess.CalledProcessError: If the remux fails.
          FileNotFoundError: If input file is not found.
        """

        if not encrypted_path.exists():
            raise FileNotFoundError(f"File not found: {encrypted_path}")

        if not self.downloader.ffmpeg_path:
            raise RuntimeError("ffmpeg not found")

        try:
            ffmpef_cmd = [
                str(self.downloader.ffmpeg_path),
                "-loglevel",
                "info",
                "-y",
                "-decryption_key",
                decryption_key,
                "-i",
                str(encrypted_path),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(remuxed_path),
            ]

            subprocess.run(
                ffmpef_cmd,
                check=True,
                **self.downloader.subprocess_aditional_args,
            )

            self.logger.info(f"Succesfully remuxed to: {remuxed_path}")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error remuxing file: {e}")
            if remuxed_path.exists():
                remuxed_path.unlink()
            raise
