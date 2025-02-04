import asyncio
import json
import logging

from enums import SongCodec
from legacy_download import DownloaderSongLegacy
from song import Song


async def main() -> None:
    """Main function for downloading the song."""
    logger = logging.getLogger(__name__)

    # Get TouchDesigner parameters
    token = parent().par.Usermediatoken.eval()  # type: ignore
    url = parent().par.Url.eval()  # type: ignore

    # Error if data is not found
    if not token or not url:
        error_msg = "Media User Token or URL not found"
        op("/project1/out_text").text = str(error_msg)  # type: ignore
        raise ValueError(error_msg)

    try:
        # Initialize downloader
        codec = SongCodec.AAC_LEGACY
        legacy = DownloaderSongLegacy(codec, token)

        # Get song info
        song_info = legacy.downloader.app.get_song_info(url)
        webPlayback = legacy.downloader.app.get_web_playback(song_info["id"])[0]

        # Get stream info and decryption key
        stream_info = await legacy.get_stream_info(webPlayback)
        decryption_key = await legacy.get_decryption_key(
            stream_info.pssh, song_info["id"]
        )

        # Set paths
        encrypted_path = legacy.get_encrypted_path(song_info["id"])
        remuxed_path = legacy.get_remuxed_path(song_info["id"])

        # Download and remux the song
        legacy.downloader.download(encrypted_path, stream_info.stream_url)
        legacy.remux(encrypted_path, remuxed_path, decryption_key)

        # Apply metadata
        tags = legacy.downloader.getTags(webPlayback)
        cover_url = legacy.downloader.getCoverUrl(
            song_info["attributes"]["artwork"]["url"]
        )
        cover_file = legacy.downloader.downloadCoverFile(cover_url)
        legacy.downloader.applyTags(remuxed_path, tags, cover_url)

        # Move the song to the final path
        final_path = legacy.get_final_path()
        legacy.downloader.moveToFinalPath(remuxed_path, final_path)

        # Create the Song object
        song = Song(song_info, cover_file)
        song_json = song.get_data()

        # Output and update TouchDesigner content
        op("request_output").text = json.dumps(song_json)  # type: ignore
        op("/project1/creep1").par.reset.pulse()  # type: ignore
        parent().par.Songreload.pulse()  # type: ignore

    except Exception as e:
        logger.error(f"Error: {e}")
        op("/project1/out_text").text = "Error: " + str(e)  # type: ignore
        raise


# Run async main
if __name__ == "__main__":
    asyncio.run(main())
else:
    # Run in loop for TouchDesigner compatibility
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
