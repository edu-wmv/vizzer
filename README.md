# vizzer

![Vizzer](./assets/image.png)

Vizzer (formerly _Lyricfy_) is a TouchDesigner project that integrates with Apple Music to download songs, extract synchronized lyrics (including syllable-level timing), and generate dynamic 3D lyric visualizations in real-time.

## Features

- **Apple Music Integration:** Download high-quality audio directly from an Apple Music song URL.
- **Synchronized Lyrics:** Extracts time-synced lyrics, including both standard TTML and syllable-level timing data when available.
- **Audio Processing:** Automatic Widevine DRM decryption and MP4 remuxing.
- **Metadata & Album Art:** Fetches song metadata, applies MP4 tags, and extracts color palettes from the album cover (using Pylette).
- **TouchDesigner Integration:** Feeds the downloaded audio, parsed lyrics, and color data directly into TouchDesigner to drive a 3D text visualization system.

## Prerequisites

- **TouchDesigner** (Commercial or Non-Commercial)
- **Python** (matching your TouchDesigner's Python version, e.g., 3.9 or 3.11)
- **FFmpeg**: Required for audio remuxing. Ensure it is installed and accessible in your system's PATH.
- **Apple Music Subscription**: You need a valid Media User Token from an active Apple Music web session.

## Installation & Setup

1. **Clone or Download the Repository:**
   Ensure you have all the files in the directory.

2. **Install Python Dependencies:**
   It is recommended to install the dependencies in a dedicated environment or the custom Python environment you use for TouchDesigner.
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure TouchDesigner Python Path:**
   Open TouchDesigner, go to **Edit > Preferences > Python**, and set your Python 64-bit Module Path to the `site-packages` directory where you installed the `requirements.txt`.

## Usage

1. Open `lyricfy.toe` in TouchDesigner.
2. Locate the main component parameters for Lyricfy.
3. **Media User Token:** Paste your Apple Music Media User Token in the `Usermediatoken` parameter.
   - *How to find it:* Open Apple Music in your web browser, open the Developer Tools (F12), go to the Network tab, play a song, and inspect the headers of the API requests to find the `media-user-token`.
4. **URL:** Paste the Apple Music URL of the song you want to visualize in the `Url` parameter.
5. Trigger the process. The Python script (`main.py`) will automatically:
   - Authenticate and fetch song metadata.
   - Download the audio stream and decrypt it.
   - Remux the audio and apply ID3 tags and album cover.
   - Parse the synchronized lyrics.
   - Pulse the TouchDesigner nodes to reload the new song and reset the 3D text visualization.

## Project Structure

- `lyricfy.toe`: The main TouchDesigner project file.
- `main.py`: The main entry point script triggered by TouchDesigner.
- `scripts/`: Contains the core Python modules:
  - `applemusic.py`: Apple Music API client.
  - `downloader.py`: Handles audio stream downloading, decryption (Widevine), and tagging.
  - `song.py`: Data model representing a Song and its lyrics/metadata.
  - `legacy_download.py` / `hardcoded_wvd.py`: Fallback and DRM handling utilities.
- `requirements.txt`: Python package dependencies.
- `Backup/` & `Audio/`: Target directories for downloaded and remuxed files.

## Disclaimer

This project is for educational and personal use only. Downloading and decrypting DRM-protected media from Apple Music may violate their Terms of Service. The maintainers of this repository are not responsible for any misuse of this tool.
