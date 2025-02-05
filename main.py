import asyncio
import json
import logging
from pathlib import Path

from scripts import AppConfig, AppleMusicAPI, LegacyDownloader, SongCodec

# from enums import SongCodec
# from legacy_download import DownloaderSongLegacy
# from song import Song


async def main() -> None:
    """Main function for downloading the song."""
    logger = logging.getLogger(__name__)

    # Get TouchDesigner parameters
    # token = parent().par.Usermediatoken.eval()  # type: ignore
    # url = parent().par.Url.eval()  # type: ignore

    token = "ArH0orYv8OPC4JCIyP1dnR1es8UyvAb+M7XhMAqrBjwHoKJDqoI5wxTly6l6t8iFb3Xf1HCyla0SE3ihmZQjQ0gdixevBuyNbkdBOw3KAJt614ILEzxs76HRnfL92Bm8u2BfCiaJS0hsUwD2qtgCYDKpYvR3p/wWBBQ1W1lw++9agu/wvbyEYUla9wTQ7Jo/lVxoTxkzhC0tXqZG1Gra0gTz8HtyDClBLIzSVN2jm0XPruYTeQ=="
    url = (
        "https://music.apple.com/br/album/texas-hold-em/1730408497?i=1730408498&l=en-GB"
    )

    # Error if data is not found
    if not token or not url:
        error_msg = "Media User Token or URL not found"
        op("/project1/out_text").text = str(error_msg)  # type: ignore
        raise ValueError(error_msg)

    try:
        # Initialize downloader
        config = AppConfig(
            token=token,
            temp_path=Path("./tmp"),
            final_path=Path("./Audio"),
            cover_size=1000,
            log_level=logging.INFO,
            ffmpeg_path=Path("/opt/homebrew/bin/ffmpeg"),
        )

        async with LegacyDownloader(SongCodec.AAC_LEGACY, config) as legacy:
            api = AppleMusicAPI(token)
            song_info = api.get_song_info(url)
            web_playback = api.get_web_playback(song_info["id"])[0]

            stream_info = await legacy.get_stream_info(web_playback)

            await legacy.process_download(song_info["id"], stream_info)

            cover_url = legacy.downloader.get_cover_url(
                song_info["attributes"]["artwork"]["url"]
            )
            tags = legacy.downloader.get_tags(web_playback)

    except Exception as e:
        logger.error(f"Error downloading song: {e}")
        # op("/project1/out_text").text = str(e)


# Run async main
if __name__ == "__main__":
    asyncio.run(main())
else:
    # Run in loop for TouchDesigner compatibility
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
