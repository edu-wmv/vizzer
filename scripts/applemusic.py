import json
import logging
import re
from typing import Any, Dict
from urllib.parse import urljoin

import requests
from checker import AppleMusicURLChecker
from constants import HEADERS, MAX_RETRIES, REQUEST_TIMEOUT, URL


class AppleMusicAPIError(Exception):
    """Custom exception for handling Apple Music API errors."""

    pass


class AppleMusicAPI:
    """
    Apple Music API client for handling authentication and requests.
    """

    def __init__(self, user_token: str, log_level: int = logging.INFO) -> None:
        """
        Initialize Apple Music API client.

        Args:
          user_token (str): User token for Apple Music API authentication.
          log_level (int, optional): Log level for the logger instance. Defaults to logging.INFO.

        Raises:
          AppleMusicAPIError: If initialization fails.
        """
        self._setup_logging(log_level)
        self._validate_token(user_token)

        self.session = self._create_session()
        self._MUT = user_token
        self.checker = AppleMusicURLChecker()

        try:
            self._set_mut()
            self._get_access_token()
            self._get_media_user_token()
        except Exception as e:
            self.logger.error(f"Error initializing Apple Music API: {str(e)}")
            raise AppleMusicAPIError("Error initializing Apple Music API")

    def _setup_logging(self, log_level: int) -> None:
        """Configure logging for the AppleMusicAPI instance."""

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _validate_token(self, user_token: str) -> None:
        """Validate user token"""

        if not user_token:
            raise AppleMusicAPIError("User token cannot be empty.")

    def _create_session(self) -> requests.Session:
        """Create a new requests session."""

        session = requests.Session()
        session.headers.update(HEADERS)
        return session

    def _set_mut(self) -> None:
        """Set the media user token for the session."""
        self.MUT = self._MUT
        self.session.headers.update({"media-user-token": self.MUT})
        self.logger.debug("Media User Token set")

    def _make_request(
        self, method: str, base_url: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with retry logic.

        Args:
          method (str): HTTP method for the request.
          endpoint (str): URL endpoint for the request.
          **kwargs: Additional keyword arguments for the request.

        Returns:
          requests.Response: Response object from the request.
        """

        url = urljoin(base_url, endpoint)
        self.logger.debug(f"Making request: {method} {url}")
        retries = 0

        while retries < MAX_RETRIES:
            try:
                response = self.session.request(
                    method, url, timeout=REQUEST_TIMEOUT, **kwargs
                )
                return response
            except requests.RequestException as e:
                retries += 1
                if retries == MAX_RETRIES:
                    raise AppleMusicAPIError(f"Error making request: {str(e)}")
                self.logger.warning(f"Retry {retries}/{MAX_RETRIES} for {url}")

    def _get_access_token(self) -> None:
        """Fetch access token from Apple Music."""

        try:
            response = self._make_request("GET", URL["BASE_URL"], "/us/browse")
            if response.status_code != 200:
                raise AppleMusicAPIError(
                    f"Error while loading main page: {response.status_code}"
                )

            index_js = re.search(r'(?<=index)(.*?)(?=\.js")', response.text)
            if not index_js:
                raise AppleMusicAPIError("Failed to get index.js")

            js_url = f"https://music.apple.com/assets/index{index_js.group(1)}.js"
            response = self._make_request("GET", URL["BASE_URL"], js_url)
            if response.status_code != 200:
                raise AppleMusicAPIError(
                    f"Error while loading index.js: {response.status_code}"
                )

            accessToken = re.search('(?=eyJh)(.*?)(?=")', response.text).group(1)
            self.session.headers.update({"Authorization": "Bearer " + accessToken})
            self.logger.info("Access token retrieved")
        except Exception as e:
            self.logger.error(f"Access token retrieval failed: {str(e)}")
            raise AppleMusicAPIError(f"Error getting access token: {str(e)}")

    def _get_media_user_token(self) -> None:
        """
        Retrieve and set media user token for API authentication.

        Raises:
          AppleMusicAPIError: If media user token cannot be retrieved.
        """
        try:
            response = self._make_request("GET", URL["AMP_API"], "/v1/me/storefront")
            data = response.json()

            self.storefront = data["data"][0]["id"]
            self.language = data["data"][0]["attributes"]["defaultLanguageTag"]

            self.logger.info("Media User Token retrieved")

        except Exception as e:
            self.logger.error(f"Error getting media user token: {str(e)}")
            raise AppleMusicAPIError(f"Media User Token retrieval failed: {str(e)}")

    def get_song_info(self, url: str) -> Dict[str, Any]:
        """
        Get song information from Apple Music URL.

        Args:
          url (str): Apple Music URL

        Returns:
          Dict[str, Any]: Song information from the URL.

        Raises:
          AppleMusicAPIError: If song info cannot be retrieved.
        """
        try:
            info = self.checker.get_url_info(url)
            if not info.is_valid:
                raise AppleMusicAPIError("Invalid URL")

            endpoint = f"/v1/catalog/{self.storefront}/{info.kind}/{info.track_id}"
            params = {
                "include[songs]": "lyrics,syllable-lyrics",
                "l": self.language,
            }

            response = self._make_request(
                "GET", URL["AMP_API"], endpoint, params=params
            )

            self.logger.info("Song Info retrieved successfully")
            return response.json()["data"][0]

        except Exception as e:
            self.logger.error(f"Error getting song info: {str(e)}")
            raise AppleMusicAPIError(f"Song info retrieval failed: {str(e)}")

    def get_web_playback(self, track_id: str) -> Dict[str, Any]:
        """
        Get web playback data for the song.

        Args:
          track_id (str): Track ID for the song.

        Returns:
          Dict[str, Any]: Web playback data for the song.

        Raises:
          AppleMusicAPIError: If web playback data cannot be retrieved.
        """
        try:
            response = self._make_request(
                "POST",
                URL["WEBPLAYBACK"],
                "",
                json={"salableAdamId": track_id, "language": self.language},
            )

            web_playback = response.json().get("songList")
            if not web_playback:
                raise AppleMusicAPIError("Web Playback data not found")

            self.logger.info("Web Playback retrieved successfully")
            return web_playback
        except Exception as e:
            self.logger.info(f"Error getting web playback: {str(e)}")
            raise AppleMusicAPIError(f"Web Playback retrieval failed: {str(e)}")

    def get_widevine_license(
        self, track_id: str, track_uri: str, challenge: str
    ) -> str:
        """
        Get Widevine license for the song.

        Args:
          track_id (str): Track ID for the song.
          track_uri (str): Track URI for the song.
          challenge (str): Challenge string for the song.

        Returns:
          str: Widevine license for the song.

        Raises:
          AppleMusicAPIError: If Widevine license cannot be retrieved.
        """
        try:
            response = self._make_request(
                "POST",
                URL["LICENSE_API"],
                "",
                json={
                    "challenge": challenge,
                    "key-system": "com.widevine.alpha",
                    "uri": track_uri,
                    "adamId": track_id,
                    "isLibrary": False,
                    "user-initiated": True,
                },
            )

            license_data = response.json().get("license")
            if not license_data:
                raise AppleMusicAPIError("License data not found")

            self.logger.info("Widevine license retrieved successfully")
            return license_data
        except Exception as e:
            self.logger.error(f"Error getting Widevine license: {str(e)}")
            raise AppleMusicAPIError(f"Widevine license retrieval failed: {str(e)}")
