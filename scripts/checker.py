import logging
import ssl
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urlparse
from urllib.request import urlopen

from models import URLInfo


class URLCheckError(Exception):
    """Custom exception for URL checking errors"""

    pass


class AppleMusicURLChecker:
    """Handles validation and parsing of Apple Music URLs"""

    APPLE_MUSIC_DOMAIN = "music.apple.com"
    HTTPS_PREFIX = "https://"

    def __init__(self, log_level: int = logging.INFO) -> None:
        """Initialize the AppleMusicURLChecker instance"""
        self._setup_logging(log_level)

    def _setup_logging(self, log_level: int) -> None:
        """Configure logging for the AppleMusicURLChecker instance"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _parse_url(self, url: str) -> ParseResult:
        """Parse URL string into components"""

        try:
            return urlparse(url)
        except Exception as e:
            raise URLCheckError(f"Invalid URL format: {str(e)}")

    def check_url(self, url: str) -> bool:
        """
        Validate if URL is a valid Apple Music URL.

        Args:
          url (str): URL to validate

        Returns:
          bool: True if URL is valid, False otherwise

        Raises:
          URLCheckError: If URL is invalid or unreachable
        """
        try:
            if not url:
                raise URLCheckError("URL cannot be empty.")

            parsed_url = self._parse_url(url)
            if not parsed_url.scheme:
                url = f"{self.HTTPS_PREFIX}{url}"
                parsed_url = self._parse_url(url)

            if parsed_url.netloc != self.APPLE_MUSIC_DOMAIN:
                self.logger.warning(f"Invalid domain: {parsed_url.netloc}")
                return False

            context = ssl._create_unverified_context()  # running td on macos require
            urlopen(url, context=context)
            return True

        except (URLError, HTTPError) as e:
            self.logger.error(f"Error checking URL: {e}")
            return False

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return False

    def get_url_info(self, url: str) -> URLInfo:
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
