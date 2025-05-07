import logging
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from Pylette import extract_colors


class SongError(Exception):
    """Custom exception for Song class"""

    pass


class Song:
    """
    Represents a song object with metadata and lyrics.

    Attributes:
      name (str): Song name.
      artist_name (str): Artist name.
      duration (int): Song duration in milliseconds.
      cover_file (str): Path to the song cover file.
    """

    def __init__(self, data: Dict[str, Any], cover_file: str) -> None:
        """
        Initialize Song instance.

        Args:
          data (Dict[str, Any]): Song data from Apple Music API.
          cover_file (str): Path to the song cover file

        Raises:
          SongError: If initialization fails.
        """
        self._setup_logging()
        self._validate_inputs(data, cover_file)
        self._set_data(data, cover_file)

    def _setup_logging(self) -> None:
        """Configure logging for the Song instance."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _validate_inputs(self, data: Dict[str, Any], cover_file: str) -> None:
        """Validate initialization inputs."""
        if not data:
            raise SongError("Song data cannot be empty.")
        if not cover_file:
            raise SongError("Cover file path cannot be empty.")

    def _set_data(self, data: Dict[str, Any], cover_file: str) -> None:
        """Set the song data attributes."""
        try:
            self.data = data
            self.ttml = data["relationships"]["lyrics"]["data"][0]["attributes"].get(
                "ttml"
            )
            self.name = data["attributes"].get("name")
            self.artistName = data["attributes"].get("artistName")
            self.duration = data["attributes"].get("durationInMillis")
            self.cover_file = cover_file
        except KeyError as e:
            raise SongError(f"Error setting song data: {str(e)}")

    def _get_timestamp(self, ts: str) -> str:
        """Convert timestamp to MM:SS format."""
        try:
            ts = ts.replace("s", "")
            secs = float(ts.split(":")[-1])

            if ":" in ts:
                mins = ts.split(":")[-2]
            else:
                mins = int(str(secs / 60)[:1])
                secs = float(str(secs % 60))

            return f"{mins:0>2}:{secs:06.3f}"
        except ValueError as e:
            self.logger.error(f"Invalid timestamp format: {str(e)}")

    def _get_miliseconds(self, time: str) -> float:
        """Convert timestamp to milliseconds."""
        try:
            self.logger.debug(f"Converting time: {time}")
            minutes, seconds = time.split(":")
            total_milliseconds = (int(minutes) * 60 * 1000) + (float(seconds) * 1000)
            self.logger.debug(f"Time in milliseconds: {total_milliseconds}")
            return total_milliseconds
        except ValueError as e:
            self.logger.error(f"Invalid time format: {str(e)}")
            raise SongError(f"Invalid time format: {str(e)}")

    def _hex_to_rgb(self, hex_color: str) -> str:
        """Convert hex color to RGB format."""
        try:
            return ",".join(str(int(hex_color[i : i + 2], 16) / 255) for i in (0, 2, 4))
        except ValueError as e:
            self.logger.error(f"Invalid hex color format: {str(e)}")
            raise SongError(f"Invalid hex color format: {str(e)}")

    def _get_colors(self) -> List[str]:
        """Extract color palette from the cover art."""
        try:
            palette = extract_colors(image=self.cover_file, palette_size=4, resize=True)
            self.logger.info(f"Extracted {len(palette)} colors from cover art")

            return [",".join(str(int(x)) for x in color.rgb) for color in palette]
        except Exception as e:
            self.logger.error(f"Error extracting colors: {str(e)}")
            return ["100,100,100"]  # Fallback color

    def _process_basic_info(self, ttml: BeautifulSoup) -> Dict[str, Any]:
        """
        Process basic song info.

        Args:
          ttml (BeautifulSoup): BeautifulSoup object containing TTML data.

        Returns:
          Dict[str, Any]: Basic song metadata.

        Raises:
          SongError: If processing fails.
        """

        try:
            songwriters = []
            songwriter = ttml.find_all("songwriter")
            if len(songwriter) > 0:
                for sw in songwriter:
                    songwriters.append(sw.text)

            return {
                "name": self.name,
                "artist": self.artistName,
                "duration": self.duration,
                "cover": self.cover_file,
                "songwriter": ", ".join(songwriters),
            }
        except Exception as e:
            self.logger.error(f"Error processing basic info: {str(e)}")
            raise SongError(f"Error processing basic info: {str(e)}")

    def _process_lyrics(self, ttml: BeautifulSoup) -> Dict[str, Any]:
        """
        Process TTML lyrics data.

        Args:
          ttml (BeautifulSoup): BeautifulSoup object containing TTML data.

        Returns:
          Dict[str, Any]: Processed lyrics data with timestamps.

        Raises:
          SongError: If processing fails.
        """

        try:
            lyrics = []
            time_synced_lyrics = []
            info = self._process_basic_info(ttml)

            timing_attr = ttml.find("tt")
            has_timing = timing_attr and timing_attr.get("itunes:timing")

            for line in ttml.find_all("p"):
                lyrics.append(line.text)

                if has_timing:
                    # if "span" in str(line):
                    #     # Handle word-by-word timing
                    #     span_soup = BeautifulSoup(str(line), "html.parser")
                    #     for span in span_soup.find_all(
                    #         "span", attrs={"begin": True, "end": True}
                    #     ):
                    #         begin = self._get_timestamp(span.get("begin"))
                    #         time_synced_lyrics.append(
                    #             {
                    #                 "time": begin,
                    #                 "timeMs": self._get_miliseconds(span.get("begin")),
                    #                 "text": span.text,
                    #             }
                    #         )
                    # else:
                    # Handle line-by-line timing
                    begin = self._get_timestamp(line.get("begin"))
                    end = self._get_timestamp(line.get("end"))

                    if begin and end:
                        time_synced_lyrics.append(
                            {
                                "beginTime": begin,
                                "beginTimeMs": self._get_miliseconds(begin),
                                "endTime": end,
                                "endTimeMs": self._get_miliseconds(end),
                                "text": line.text,
                            }
                        )

            info["lyrics"] = lyrics
            if time_synced_lyrics:
                info["timeSyncedLyrics"] = time_synced_lyrics

            self.logger.info(f"Processed {len(lyrics)} lyrics lines")
            return info
        except Exception as e:
            self.logger.error(f"Error processing lyrics: {str(e)}")
            raise SongError(f"Error processing lyrics: {str(e)}")

    def get_data(self) -> Dict[str, Any]:
        """
        Get processed song data with lyrics and metadata.

        Returns:
          Dict[str, Any]: Processed song data.

        Raises:
          SongError: If data processing fails.
        """
        try:
            ttml = BeautifulSoup(self.ttml, "html.parser")
            info = self._process_lyrics(ttml)
            info["colors"] = self._get_colors()

            if bg_color := self.data["attributes"]["artwork"].get("bgColor"):
                info["bgColor"] = self._hex_to_rgb(bg_color)

            self.logger.info("Song data processed successfully")
            return info

        except Exception as e:
            self.logger.error(f"Error processing data: {str(e)}")
            raise SongError(f"Error processing data: {str(e)}")
