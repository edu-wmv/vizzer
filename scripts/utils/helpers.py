from pathlib import Path

import requests


class LyrikitHelper:
    def __init__(self) -> None:
        pass

    @staticmethod
    def getURLResponseBytes(url: str) -> bytes:
        """Get the response bytes from the URL."""
        return requests.get(url).content

    @staticmethod
    def getSongOnPath(path: Path, id: str) -> Path:
        """Get the path for the file on the given path."""
        return path / f"{id}.m4a"

    @staticmethod
    def moveFile(src: Path, dest: Path) -> None:
        """Move the file from source to destination."""
        src.replace(dest)
