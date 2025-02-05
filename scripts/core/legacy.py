import asyncio
import base64
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import m3u8
from pywidevine import PSSH
from pywidevine.license_protocol_pb2 import WidevinePsshData

from scripts.core.downloader import Downloader
from scripts.core.models import StreamInfo
from scripts.exceptions import LegacyDownloadError, StreamInfoError
from scripts.utils.config import AppConfig
from scripts.utils.constants import FFMPEG_ARGS
from scripts.utils.enums import SongCodec
from scripts.utils.helpers import LyrikitHelper


class LegacyDownloader:
    """
    Legacy song downloader implementation for handling specific codec formats.

    This class manages the download of audio streams using legacy codecs,
    specifically AAC-HE-Legacy and AAC-Legacy.
    """

    def __init__(self, codec: SongCodec, config: AppConfig) -> None:
        self.codec = codec
        self.downloader = Downloader(config)
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self) -> "LegacyDownloader":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if hasattr(self.downloader, "cleanup"):
            await self.downloader.cleanup()

    async def get_stream_info(self, web_playback: Dict[str, Any]) -> StreamInfo:
        """
        Get the stream info for the song from the web playback data.

        Args:
          web_playback (Dict[str, Any]): Web playback data for the song.

        Returns:
          Stream info for the song.

        Raises:
          StreamInfoError: If stream info cannot be retrieved.
        """
        flavor = self._get_flavor_for_codec()
        stream_info = StreamInfo()

        stream_url = self._extract_stream_url(web_playback, flavor)
        if not stream_url:
            raise StreamInfoError(f"No stream for codec {self.codec.value}")

        m3u8_obj = await self._load_m3u8(stream_url)
        if not m3u8_obj.keys:
            raise StreamInfoError("PSSH keys not found in M3U8 playlist")

        stream_info.stream_url = stream_url
        stream_info.pssh = m3u8_obj.keys[0].uri
        stream_info.codec = self.codec

        return stream_info

    async def process_download(self, track_id: str, stream_info: StreamInfo) -> None:
        """
        Process the download of the song using the stream info.

        Args:
          track_id (str): Track ID for the song.
          stream_info (StreamInfo): Stream info for the song.

        Raises:
          LegacyDownloadError: If the download process fails.
        """
        try:
            encrypted_path = LyrikitHelper.getSongOnPath(
                self.downloader.temp_path, track_id
            )
            remuxed_path = LyrikitHelper.getSongOnPath(
                self.downloader.output_path, "audio"
            )

            self.downloader.download(encrypted_path, stream_info.stream_url)

            key = self.get_decryption_key(stream_info.pssh, track_id)
            await self.remux(encrypted_path, remuxed_path, key)

        except Exception as e:
            self.logger.error(f"Error processing download: {e}")
            raise LegacyDownloadError(f"Error processing download: {e}")

    def _get_flavor_for_codec(self) -> str:
        """
        Get the flavor for the current codec.

        Returns:
          str: Flavor for the codec.
        """
        return "32:ctrp64" if self.codec == SongCodec.AAC_HE_LEGACY else "28:ctrp256"

    def _extract_stream_url(
        self, web_playback: Dict[str, Any], flavor: str
    ) -> Optional[str]:
        """
        Extract the stream URL from the web playback data.

        Args:
          web_playback (Dict[str, Any]): Web playback data for the song.
          flavor (str): Flavor for the codec.

        Returns:
          str: Stream URL for the song.

        Raises:
          StreamInfoError: If stream URL cannot be extracted.
        """
        try:
            return next(
                x["URL"] for x in web_playback["assets"] if x["flavor"] == flavor
            )
        except StopIteration:
            raise StreamInfoError("Stream URL not found in web playback data")

    async def _load_m3u8(self, url: str) -> m3u8.M3U8:
        """
        Load the M3U8 playlist from the given URL.

        Args:
          url (str): URL of the M3U8 playlist.

        Returns:
          m3u8.M3U8: M3U8 playlist object.

        Raises:
          LegacyDownloadError: If the M3U8 playlist cannot be loaded.
        """
        try:
            return m3u8.load(uri=url, verify_ssl=False)
        except Exception as e:
            self.logger.error(f"Error loading M3U8 playlist: {e}")
            raise LegacyDownloadError(f"Error loading M3U8 playlist: {e}")

    def get_decryption_key(self, pssh: str, track_id: str) -> str:
        """
        Get the decryption key for the encrypted content.

        Args:
          pssh (str): PSSH key for the content.
          track_id (str): Track ID for the song.

        Returns:
          str: Decryption key for the content.

        Raises:
          LegacyDownloadError: If the decryption key cannot be retrieved.
        """

        try:
            pssh_obj = self._prepare_widevine_pssh(pssh)

            cdm_session = self.downloader.cdm.open()

            try:
                challenge = self._get_license_challenge(cdm_session, pssh_obj)

                license_b64 = self.downloader.api.get_widevine_license(
                    track_id=track_id, track_uri=pssh, challenge=challenge
                )

                key = self._extract_content_key(cdm_session, license_b64)
                self.logger.info(f"Content key extracted successfully: {key}")
                return key
            finally:
                self.downloader.cdm.close(cdm_session)

        except Exception as e:
            self.logger.error(f"Error getting decryption key: {e}")
            raise LegacyDownloadError(f"Error getting decryption key: {e}")

    def _prepare_widevine_pssh(self, pssh: str) -> PSSH:
        try:
            wdv_pssh_data = WidevinePsshData()
            wdv_pssh_data.algorithm = 1
            wdv_pssh_data.key_ids.append(base64.b64decode(pssh.split(",")[1]))

            return PSSH(wdv_pssh_data.SerializeToString())
        except Exception as e:
            self.logger.error(f"Error preparing Widevine PSSH: {e}")
            raise LegacyDownloadError(f"Error preparing Widevine PSSH: {e}")

    def _get_license_challenge(self, cdm_session: Any, pssh: PSSH) -> str:
        """
        Get license challenge for Widevine.

        Args:
          cdm_session (Any): CDM session object.
          pssh (PSSH): PSSH object.

        Returns:
          Base64 encoded challenge string.
        """
        try:
            challenge = self.downloader.cdm.get_license_challenge(cdm_session, pssh)
            return base64.b64encode(challenge).decode()
        except Exception as e:
            self.logger.error(f"Error getting license challenge: {e}")
            raise LegacyDownloadError(f"Error getting license challenge: {e}")

    def _extract_content_key(self, cdm_session: Any, license_b64: str) -> str:
        """
        Extract content key from license response.

        Args:
          cdm_session (Any): CDM session object.
          license_b64 (str): Base64 encoded license response.

        Returns:
          Hex string of content key
        """

        try:
            self.downloader.cdm.parse_license(cdm_session, license_b64)

            for key in self.downloader.cdm.get_keys(cdm_session):
                if key.type == "CONTENT":
                    return key.key.hex()

            raise LegacyDownloadError("Content key not found in license response")

        except Exception as e:
            self.logger.error(f"Error extracting content key: {e}")
            raise LegacyDownloadError(f"Error extracting content key: {e}")

    async def remux(self, encrypted_path: Path, output_path: Path, key: str) -> None:
        """
        Remix encrypted content with decryption key.

        Args:
          encrypted_path (Path): Path to encrypted content.
          output_path (Path): Path to output content.
          key (str): Decryption key.

        Raises:
          LegacyDownloadError: If remuxing fails.
        """
        try:
            command = self._prepare_ffmpeg_command(encrypted_path, output_path, key)
            print(command)

            process = await asyncio.create_subprocess_exec(
                *command, **self.downloader.subprocess_args
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise LegacyDownloadError(
                    f"FFmpeg process failed with code {process.returncode}: {stderr.decode()}"
                )

            self.logger.info(f"Content remuxed successfully to {output_path}")

        except Exception as e:
            self.logger.error(f"Error preparing FFmpeg command: {e}")
            raise LegacyDownloadError(f"Error preparing FFmpeg command: {e}")

    def _prepare_ffmpeg_command(
        self, input_path: Path, ouput_path: Path, key: str
    ) -> list:
        return [
            str(self.downloader.config.ffmpeg_path),
            "-y",
            "-decryption_key",
            key,
            "-i",
            str(input_path),
            *FFMPEG_ARGS,
            str(ouput_path),
        ]
