"""Apple Music API client module."""

import logging
import re
import ssl
from dataclasses import dataclass
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import requests

# from scripts.core.models import URLInfo
from scripts.exceptions import AppleMusicAPIError, URLCheckError
from scripts.utils.constants import HEADERS, URL


@dataclass
class URLInfo:
    """Data class to store URL parsing results"""

    track_id: str
    kind: str
    is_valid: bool = False


class AppleMusicURLChecker:
    """Handles validation and parsing of Apple Music URLs."""

    APPLE_MUSIC_DOMAINS = "music.apple.com"
    HTTPS_PREFIX = "https://"

    def __init__(self, log_level: int = logging.INFO) -> None:
        """
        Initialize the AppleMusicURLChecker instance.

        Args:
          log_level (int): Log level for the logger instance. Defaults to logging.INFO.

        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

    def get_data_from_url(self, url: str) -> URLInfo:
        """
        Extract track information from Apple Music URL.

        Args:
          url (str): Apple Music URL to parse

        Returns:
          URLInfo: Parsed URL information

        Raises:
          URLCheckError: If URL parsing fails
        """

        try:
            if not self.check_url(url):
                return URLInfo("", "", False)

            path_parts = url.split("/")
            track_id = path_parts[-1]
            kind = path_parts[4]

            if kind == "album":
                track_parts = track_id.split("?i=")
                if len(track_parts) > 1:
                    track_id = track_parts[1].split("&")[0]
                    kind = "songs"

            return URLInfo(track_id, kind, True)

        except Exception as e:
            self.logger.error(f"URL info extraction failed: {e}")
            raise URLCheckError(f"Error parsing URL: {str(e)}")

    def check_url(self, url: str) -> bool:
        """
        Validate if URL is a valid Apple Music URL.

        Args:
          url (str): URL to validate.

        Returns:
          bool: True if URL is valid, False otherwise.

        Raises:
          URLCheckError: If URL is invalid on unreachable.
        """

        if not url:
            raise URLCheckError("URL cannot be empty.")

        try:
            parsed_url = self._parse_url(url)
            if parsed_url.netloc != self.APPLE_MUSIC_DOMAINS:
                self.logger.warning(f"Invalid domain: {parsed_url.netloc}")
                return False

            context = ssl._create_unverified_context()
            urlopen(url, context=context)
            return True

        except (URLError, HTTPError) as e:
            self.logger.error(f"Error checking URL: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected erro: {str(e)}")
            return False

    def _parse_url(self, url: str) -> urlparse:
        """
        Parse and normalize URL string.

        Args:
          url (str): URL to parse.

        Returns:
          ParseResult object containing the parsed URL components.

        Raises:
          URLCheckError: If URL is invalid.
        """

        try:
            if not url.startswith(self.HTTPS_PREFIX):
                url = f"{self.HTTPS_PREFIX}{url}"
            return urlparse(url)
        except Exception as e:
            raise URLCheckError(f"Invalid URL format: {str(e)}")


class AppleMusicAPI:
    """Apple Music API client for handling authentication and requests."""

    def __init__(self, user_token: str, log_level: int = logging.INFO) -> None:
        """
        Initialize Apple Music API client.

        Args:
          user_token (str): User token for Apple Music API authentication.
          log_level (int, optional): Log level for the logger instance. Defaults to logging.INFO.

        Raises:
          AppleMusicAPIError: If initialization fails.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        if not user_token:
            raise AppleMusicAPIError("User token cannot be empty.")

        self._mut = user_token
        self.session = self._create_session()
        self.checker = AppleMusicURLChecker(log_level)

        try:
            self._set_mut()
            self._get_access_token()
            self._get_storefront()
        except Exception as e:
            self.logger.error(f"Error initializing Apple Music API: {str(e)}")
            raise AppleMusicAPIError(f"Failed to initialize API client: {str(e)}")

    def _create_session(self) -> requests.Session:
        """
        Create and configure requests session.

        Returns:
          Configured requests session.
        """

        session = requests.Session()
        session.headers.update(HEADERS)
        return session

    def _set_mut(self) -> None:
        """Set the media user token in the session headers."""
        self.session.headers.update({"media-user-token": self._mut})

    def _make_request(
        self, method: str, url_base: str, endpoint: str, **kwargs
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

        url = urljoin(url_base, endpoint)
        self.logger.debug(f"Making request to: {url}")
        retries = 0

        while retries < 3:
            try:
                response = self.session.request(method, url, timeout=10, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                retries += 1
                if retries == 3:
                    raise AppleMusicAPIError(f"Error making request: {str(e)}")
                self.logger.warning(f"Retry {retries}/3 for {url}")

    def _get_access_token(self) -> None:
        """
        Fetch and set access token on session.

        Raises:
          AppleMusicAPIError: If token retrieval fails.
        """

        try:
            response = self._make_request("GET", URL["BASE_URL"], "/us/browse")
            self.logger.info("Access token request successful")

            # Find index*.js to get token
            index_js = re.search(r'(?<=index)(.*?)(?=\.js")', response.text)
            if not index_js:
                raise AppleMusicAPIError("Failed to get index.js")

            js_url = f"/assets/index{index_js.group(1)}.js"
            response = self._make_request("GET", URL["BASE_URL"], js_url)

            access_token = re.search('(?=eyJh)(.*?)(?=")', response.text)
            if not access_token:
                raise AppleMusicAPIError("Failed to extract access token")

            self.session.headers.update(
                {"Authorization": f"Bearer {access_token.group(1)}"}
            )
            self.logger.info("Access token retrieved successfully")

        except Exception as e:
            self.logger.error(f"Access token retrieval failed: {str(e)}")
            raise AppleMusicAPIError(f"Failed to get acess token: {str(e)}")

    def _get_storefront(self) -> None:
        """
        Fetch and set the storefronts for API search.

        Raises:
          AppleMusicAPIError: If data fetch fails.
        """

        try:
            response = self._make_request("GET", URL["AMP_API"], "/v1/me/storefront")
            data = response.json()

            self.storefront = data["data"][0]["id"]
            self.language = data["data"][0]["attributes"]["defaultLanguageTag"]

            self.logger.info("Storefronts updated successfully")
        except Exception as e:
            self.logger.error(f"Error setting storefronts: {str(e)}")
            raise AppleMusicAPIError(f"Failed to set storefronts: {str(e)}")

    def get_song_info(self, url: str) -> Dict[str, Any]:
        """
        Retrieve song information from Apple Music API.

        Args:
          url (str): Apple Music track ID

        Returns:
          Dict containing song information

        Raises:
          AppleMusicAPIError: If API request fails
        """

        try:
            url_data = self.checker.get_data_from_url(url)
            if not url_data.is_valid:
                raise AppleMusicAPIError("Invalid URL data")

            endpoint = f"/v1/catalog/{self.storefront}/songs/{url_data.track_id}"
            response = self._make_request("GET", URL["AMP_API"], endpoint)
            return response.json().get("data")[0]
        except Exception as e:
            raise AppleMusicAPIError(f"Failed to get song info: {str(e)}")

    def get_web_playback(self, track_id: str) -> Dict[str, Any]:
        """
        Get web playback data for the song.

        Args:
          track_id (str): Apple Music track ID.

        Returns:
          Dict[str, Any]: Web playback data for the song.

        Raises:
          AppleMusicAPIError: If web playback data cannot be retrieved.
        """

        try:
            response = self._make_request(
                "POST",
                URL["WEB_PLAYBACK"],
                "",
                json={"salableAdamId": track_id, "language": self.language},
            )

            web_playback = response.json().get("songList")
            if not web_playback:
                raise AppleMusicAPIError("Web Playback data not found")

            self.logger.info("Web Playback data retrieved successfully")
            return web_playback
        except Exception as e:
            self.logger.info(f"Error getting web playback data: {str(e)}")
            raise AppleMusicAPIError(f"Web Playback retrieval failed: {str(e)}")

    def get_widevine_license(
        self, track_id: str, track_uri: str, challenge: str
    ) -> str:
        """
        Get Widevine license for the song.

        Args:
          track_id (str): Track ID for the song.
          track_uri (str): Track URI for the song.
          challenge (str): Widevine license challenge.

        Returns:
          str: Widevine license for the song.

        Raises:
          AppleMusicAPIError: If license retrieval fails.
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
                raise AppleMusicAPIError("Widevine license not found")

            self.logger.info("Widevine license retrieved successfully")
            return license_data

        except Exception as e:
            self.logger.info(f"Error getting Widevine license: {str(e)}")
            raise AppleMusicAPIError(f"Failed to get Widevine license: {str(e)}")
