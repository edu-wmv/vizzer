import shutil
import subprocess
import re
import requests
from pywidevine import Cdm, Device
from pathlib import Path
from yt_dlp import YoutubeDL
from mutagen.mp4 import MP4, MP4Cover
from applemusic import AppleMusicAPI

from constants import MP4_TAGS_MAP
from hardcoded_wvd import HARDCODED_WVD

class Downloader:
  def __init__(self, token):
    self.token = token
    self.app = AppleMusicAPI(self.token)
    self.__setCDM()
    self.__setPaths()
    self.__setSubprocessArgs()
    
    self.cover_size = 1000
    self.exclude_tags = None
    self.__setExcludeTagsList()
  
  def __setCDM(self):
    self.cdm = Cdm.from_device(Device.loads(HARDCODED_WVD))

  def __setPaths(self):
    self.temp_path = Path('./temp')
    self.final_path = Path('./Audio')
    # self.ffmpeg_path = shutil.which('ffmpeg') # fix this!!
    self.ffmpeg_path = Path('/opt/homebrew/bin/ffmpeg') # works on macos

  def __setSubprocessArgs(self):
    self.subprocess_aditional_args = {
      'stdout': subprocess.DEVNULL,
      'stderr': subprocess.DEVNULL,
    }

  def __setExcludeTagsList(self):
    self.exclude_tags_list = (
      [i.lower() for i in self.exclude_tags.split(',')]
      if self.exclude_tags
      else []
    )

  def download(self, path: Path, stream_url: str) -> None:
    with YoutubeDL(
      {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(path),
        "allow_unplayable_formats": True,
        "fixup": "never",
        "allowed_extractors": ["generic"],
        "noprogress": False,
      }
    ) as ydl:
      ydl.download([stream_url])
      print('Download OK')
    
  def getTags(self, webplayback: dict) -> dict:
    tags_raw = webplayback["assets"][0]["metadata"]
    tags = {
      "album": tags_raw["playlistName"],
      "album_artist": tags_raw["playlistArtistName"],
      "album_id": int(tags_raw["playlistId"]),
      "album_sort": tags_raw["sort-album"],
      "artist": tags_raw["artistName"],
      "artist_id": int(tags_raw["artistId"]),
      "artist_sort": tags_raw["sort-artist"],
      "comments": tags_raw.get("comments"),
      "compilation": tags_raw["compilation"],
      "composer": tags_raw.get("composerName"),
      "composer_id": (
          int(tags_raw.get("composerId")) if tags_raw.get("composerId") else None
      ),
      "composer_sort": tags_raw.get("sort-composer"),
      "copyright": tags_raw.get("copyright"),
      # "date": (
      #     self.downloader.sanitize_date(tags_raw["releaseDate"])
      #     if tags_raw.get("releaseDate")
      #     else None
      # ),
      "disc": tags_raw["discNumber"],
      "disc_total": tags_raw["discCount"],
      "gapless": tags_raw["gapless"],
      "genre": tags_raw["genre"],
      "genre_id": tags_raw["genreId"],
      # "lyrics": lyrics_unsynced if lyrics_unsynced else None,
      "media_type": 1,
      "rating": tags_raw["explicit"],
      "storefront": tags_raw["s"],
      "title": tags_raw["itemName"],
      "title_id": int(tags_raw["itemId"]),
      "title_sort": tags_raw["sort-name"],
      "track": tags_raw["trackNumber"],
      "track_total": tags_raw["trackCount"],
      "xid": tags_raw.get("xid"),
    }
    
    print('Tags OK')
    return tags
    
  def getCoverUrl(self, base_cover: str) -> str:
    final = re.sub(
      r"\{w\}x\{h\}([a-z]{2})\.jpg",
      f"{self.cover_size}x{self.cover_size}bb.jpg",
      base_cover
    )
    
    print('Cover URL OK')
    return final
  
  def downloadCoverFile(self, cover_url: str) -> None:
    response = requests.get(cover_url, stream = True)
    with open("temp/temp_cover.jpg", "wb") as f:
      for chunk in response.iter_content(chunk_size = 1024):
        f.write(chunk)
        
    return './temp/temp_cover.jpg'
  
  @staticmethod
  def getUrlResponseBytes(url: str) -> bytes:
    return requests.get(url).content
  
  def applyTags(self, remux_path: Path, tags: dict, cover_url: str) -> None:
    to_apply_tags = [
      tag_name
      for tag_name in tags.keys()
      if tag_name not in self.exclude_tags_list
    ]
    
    mp4_tags = {}
    for tag_name in to_apply_tags:
      if tag_name in ("disc", "disc_total"):
        if mp4_tags.get("disk") is None:
          mp4_tags["disk"] = [[0,0]]
        if tag_name == "disc":
          mp4_tags["disk"][0][0] = tags[tag_name]
        elif tag_name == "disc_total":
          mp4_tags["disk"][0][1] = tags[tag_name]
      elif tag_name in ("track", "track_total"):
        if mp4_tags.get("trkn") is None:
          mp4_tags["trkn"] = [[0,0]]
        if tag_name == "track":
          mp4_tags["trkn"][0][0] = tags[tag_name]
        elif tag_name == "track_total":
          mp4_tags["trkn"][0][1] = tags[tag_name]
      elif tag_name == "compilation":
        mp4_tags["cpil"] = tags["compilation"]
      elif tag_name == "gapless":
        mp4_tags["pgap"] = tags["gapless"]
      elif (
        MP4_TAGS_MAP.get(tag_name) is not None
        and tags.get(tag_name) is not None
      ):
        mp4_tags[MP4_TAGS_MAP[tag_name]] = [tags[tag_name]]
    
    if "cover" not in self.exclude_tags_list:
      mp4_tags["covr"] = [
        MP4Cover(
          self.getUrlResponseBytes(cover_url),
          imageformat=MP4Cover.FORMAT_JPEG,
        )
      ]
      
    mp4 = MP4(remux_path)
    mp4.clear()
    mp4.update(mp4_tags)
    mp4.save()
    print('Tags Apply OK')
    
  def moveToFinalPath(self, remux_path: Path, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(remux_path, final_path)
    print('Move To Final Path OK')
