import shutil
import subprocess
import m3u8
import requests
import re
import json
import os
import sys
import base64
from dotenv import load_dotenv
from pywidevine.license_protocol_pb2 import WidevinePsshData
from pywidevine import PSSH, Cdm, Device
from pathlib import Path
from yt_dlp import YoutubeDL
from mutagen.mp4 import MP4, MP4Cover
from bs4 import BeautifulSoup
#from colorthief import ColorThief
from Pylette import extract_colors

sys.path.extend(["./scripts"])
from constants import HEADERS, URL, MP4_TAGS_MAP
from checker import get_url_info
from enums import SongCodec
from hardcoded_wvd import HARDCODED_WVD
from models import StreamInfo

MEDIA_USER_TOKEN = parent().par.Usermediatoken.eval() # type: ignore
url = parent().par.Url.eval() # type: ignore

if not MEDIA_USER_TOKEN:
  exit(1)
  #raise Exception('Media User Token not found')
if not url:
  op('request_output').text = 'URL not found' # type: ignore
  exit(1)

class AppleMusicAPI:
  def __init__(self):
    self.session = requests.Session()
    self.session.headers.update(HEADERS)

    self.__setMUT()

    self.__acessToken()
    self.__mediaUserToken()

  def __setMUT(self) -> None:
    self.MUT = MEDIA_USER_TOKEN

  def __acessToken(self) -> None:
    response = requests.get('https://music.apple.com/us/browse')
    if response.status_code != 200:
      raise Exception('Error while loading main page: ' + str(response.status_code))
  
    indexJs = re.search('(?<=index)(.*?)(?=\.js")', response.text).group(1)
    response = self.session.get('https://music.apple.com/assets/index' + indexJs + '.js')
    if response.status_code != 200:
      debug('Error getting index: ' + str(response.status_code)) # type: ignore
  
    accessToken = re.search('(?=eyJh)(.*?)(?=")', response.text).group(1)
    self.session.headers.update({'Authorization': 'Bearer ' + accessToken})
    debug('Access Token ✅')

  def __mediaUserToken(self) -> None:
    self.session.headers.update({'media-user-token': self.MUT})
    response = self.session.get('https://amp-api.music.apple.com/v1/me/storefront')
    if response.status_code == 200:
      response = json.loads(response.text)
      self.storefront = response["data"][0].get("id")
      self.language = response["data"][0]["attributes"].get("defaultLanguageTag")
      self.session.headers.update({'media-user-token': self.MUT})
      debug('Media User Token ✅')
    else:
      debug('Error getting MUT: ' + str(response.status_code)) # type: ignore

  def getSongInfo(self, url: str) -> dict | None:
    info = get_url_info(url)

    if (info['kind'] != None and info['track_id'] != None):
      try:
        response = self.session.get(
          URL['SONG_INFO_BASE'] + f"{self.storefront}/{info['kind']}/{info['track_id']}",
          params = {
            'include[songs]': 'lyrics,syllable-lyrics',
            'l': f'{self.language}'
          }
        )

        if response.status_code == 200:
          debug('Song Info ✅')
          return response.json()['data'][0]
        else:
          raise Exception(str(response.status_code))
        
      except Exception as e:
        debug('Error getting song info: ' + str(e))
        debug('Song Info ❌')
        return None

  def getWebPlayback(self, track_id: str) -> dict:
    response = self.session.post(
      URL['WEBPLAYBACK'],
      json = {
        "salableAdamId": track_id,
        "language": self.language,
      }
    )

    try:
      response.raise_for_status()
      webPlayback = response.json().get("songList")
      debug('Web Playback ✅')
      assert webPlayback
    except (
      requests.HTTPError,
      requests.exceptions.JSONDecodeError,
      AssertionError
    ):
      raise Exception('Error getting web playback')
    
    return webPlayback

  def getWidevineLicense(self, track_id: str, track_uri: str, challenge: str) -> str:
    response = self.session.post(
      URL['LICENSE_API'],
      json = {
        "challenge": challenge,
        "key-system": "com.widevine.alpha",
        "uri": track_uri,
        "adamId": track_id,
        "isLibrary": False,
        "user-initiated": True
      }
    )
    
    try:
      response.raise_for_status()
      wdv_license = response.json().get("license")
      assert wdv_license
    except (
      requests.HTTPError,
      requests.exceptions.JSONDecodeError,
      AssertionError
    ):
      raise Exception('Error getting widevine license')
    
    return wdv_license

class Downloader:
  def __init__(self):
    self.app = AppleMusicAPI()
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
    self.ffmpeg_path = Path('C:/Users/montz/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-7.0-full_build/bin/ffmpeg.exe')

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
      debug('Download ✅')
    
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
    
    debug('Tags ✅')
    return tags
    
  def getCoverUrl(self, base_cover: str) -> str:
    final = re.sub(
      r"\{w\}x\{h\}([a-z]{2})\.jpg",
      f"{self.cover_size}x{self.cover_size}bb.jpg",
      base_cover
    )
    
    debug('Cover URL ✅')
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
    debug('Tags Apply ✅')
    
  def moveToFinalPath(self, remux_path: Path, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(remux_path, final_path)
    debug('Move To Final Path ✅')
  
class DownloaderSongLegacy:
  def __init__(self, codec):
    self.codec = codec
    self.downloader = Downloader()
    
  def getStreamInfo(self, webplayback: dict) -> StreamInfo:
    try:
      flavor = "32:ctrp64" if self.codec == SongCodec.AAC_HE_LEGACY else "28:ctrp256"
      stream_info = StreamInfo()
      stream_info.stream_url = next(
        x 
        for x in webplayback["assets"] 
        if x["flavor"] == flavor
      )["URL"]
      m3u8_obj = m3u8.load(stream_info.stream_url)
      stream_info.pssh = m3u8_obj.keys[0].uri
      stream_info.codec = self.codec

      if (
        stream_info.stream_url != None and 
        stream_info.pssh != None
      ):
        debug('Stream Info ✅')
        return stream_info
      else:
        raise Exception('Error getting stream info')
    except Exception as e:
      debug('Stream Info ❌: ' + str(e))
      return None

  def getDecryptionKey(self, pssh: str, track_id: str) -> str:
    try:
      wdv_pssh_data = WidevinePsshData()
      wdv_pssh_data.algorithm = 1
      wdv_pssh_data.key_ids.append(base64.b64decode(pssh.split(',')[1]))
      pssh_obj = PSSH(wdv_pssh_data.SerializeToString())
      cdm_session = self.downloader.cdm.open()
      challenge = base64.b64encode(
        self.downloader.cdm.get_license_challenge(cdm_session, pssh_obj)
      ).decode()
      license = self.downloader.app.getWidevineLicense(track_id, pssh, challenge)
      self.downloader.cdm.parse_license(cdm_session, license)
      decryption_key = next(
        x
        for x in self.downloader.cdm.get_keys(cdm_session)
        if x.type == "CONTENT"
      ).key.hex()
      
    finally:
      self.downloader.cdm.close(cdm_session)
    
    return decryption_key

  def getEncryptedPath(self, track_id: str) -> Path:
    return self.downloader.temp_path / f"{track_id}_encrypted.m4a"
  
  def getRemuxedPath(self, track_id: str) -> Path:
    return self.downloader.temp_path / f"{track_id}_remuxed.m4a"

  def getFinalPath(self) -> Path:
    return self.downloader.final_path.joinpath(*["song.m4a"])

  def remux(self, encrypted_path: Path, remuxed_path: Path, decryption_key: str) -> None:
    subprocess.run(
      [
        self.downloader.ffmpeg_path,
        "-loglevel",
        "info",
        "-y",
        "-decryption_key",
        decryption_key,
        "-i",
        encrypted_path,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        remuxed_path
      ],
      check=True,
      **self.downloader.subprocess_aditional_args
    )
    
    debug('Remux ✅')

class Song:
  def __init__(self, data: dict, cover_file: str):
    self.__setData(data)
    self.cover_file = cover_file
    
  def __setData(self, data: dict) -> None:
    self.data = data
    self.ttml = data["relationships"]["lyrics"]["data"][0]["attributes"].get("ttml")
    self.name = data["attributes"].get("name")
    self.artistName = data["attributes"].get("artistName")
    self.duration = data["attributes"].get("durationInMillis")
  
  def __getTs(self, ts: str) -> float:
    ts = ts.replace('s', '')
    secs = float(ts.split(':')[-1])
    
    if ":" in ts:
      mins = ts.split(':')[-2]
    else:
      mins = int(str(secs / 60)[:1])
      secs = float(str(secs % 60))
    
    return f'{mins:0>2}:{secs:06.3f}'
  
  def __getMs(self, time: str) -> float:
    parts = time.split(':')
    millis = 0
    
    if (len(parts) == 2):
      minutes = int(parts[0])
      seconds = float(parts[1])
      millis = (minutes * 60 + seconds) * 1000
    elif (len(parts) == 1):
      millis = float(parts[0]) * 1000
      
    return millis
  
  def __hexToRgb(self, hex: str) -> str:
    return ','.join(str(i/255) for i in tuple(int(hex[i:i+2], 16) for i in (0, 2, 4)))
  
  def __getColors(self, cover_path: str):
    #img = ColorThief(cover_path)
    
    palette = extract_colors(image=cover_path, palette_size=4, resize=True)
    cols = []
    for color in palette:
      col = color.rgb
      cols.append(','.join(str(x) for x in col))
    
    return cols
  
  def getDataFix(self) -> dict:
    ttml = BeautifulSoup(self.ttml, "html.parser")
    
    info = {}
    lyrics = []
    songwriters = []
    timeSyncedLyrics = []
    
    info["name"] = self.name
    info["artist"] = self.artistName
    info["duration"] = self.duration
    
    songwriter = ttml.find_all('songwriter')
    if len(songwriter) > 0:
      for sw in songwriter:
        songwriters.append(sw.text)
      info["songwriter"] = ", ".join(songwriters)
    
    # info["colors"] = [
    #   self.__hexToRgb(self.data["attributes"]["artwork"][color])
    #   for color in self.data["attributes"]["artwork"] 
    #   if color.startswith("textColor")
    # ]
      
    info["colors"] = self.__getColors(self.cover_file)
    print(info["colors"])
    
    if self.data["attributes"]["artwork"].get("bgColor"):
      info["bgColor"] = self.__hexToRgb(self.data["attributes"]["artwork"]["bgColor"])
    
    for line in ttml.find_all('p'):
      lyrics.append(line.text)
      
      __timing = ttml.find('tt').get("itunes:timing")
      
      if __timing != None:
        if "span" in str(line):
          span = BeautifulSoup(str(line), 'html.parser')
          
          for s in span.find_all("span", attrs={'begin': True, 'end': True}):
            begin = self.__getTs(str(s.get("begin")))
            timeSyncedLyrics.append(
              {
                "time": begin, 
                "timeMs": self.__getMs(str(s.get("begin"))), 
                "text": s.text
              }
            )
          
        else:
          timeSyncedLyrics.append(
            {
              "beginTime": self.__getTs(str(line.get("begin"))), 
              "beginTimeMs": self.__getMs(str(line.get("begin"))), 
              "endTime": self.__getTs(str(line.get("end"))),
              "endTimeMs": self.__getMs(str(line.get("end"))),
              "text": line.text
            }
          )
          
    info["lyrics"] = lyrics
    if timeSyncedLyrics: info["timeSyncedLyrics"] = timeSyncedLyrics
    
    debug('Data Fix ✅')
    return info
  
codec = SongCodec.AAC_LEGACY
legacy = DownloaderSongLegacy(codec)

song_info = legacy.downloader.app.getSongInfo(url)
webPlayback = legacy.downloader.app.getWebPlayback(song_info['id'])[0]

stream_info = legacy.getStreamInfo(webPlayback)
decryption_key = legacy.getDecryptionKey(stream_info.pssh, song_info['id'])

encrypted_path = legacy.getEncryptedPath(song_info['id'])
remuxed_path = legacy.getRemuxedPath(song_info['id'])

legacy.downloader.download(encrypted_path, stream_info.stream_url)
legacy.remux(encrypted_path, remuxed_path, decryption_key)

tags = legacy.downloader.getTags(webPlayback)
cover_url = legacy.downloader.getCoverUrl(song_info['attributes']['artwork']['url'])
cover_file = legacy.downloader.downloadCoverFile(cover_url)
legacy.downloader.applyTags(remuxed_path, tags, cover_url)

final_path = legacy.getFinalPath()
legacy.downloader.moveToFinalPath(remuxed_path, final_path)

song = Song(song_info, cover_file)
song_json = song.getDataFix()

op('request_output').text = json.dumps(song_json) # type: ignore
parent().par.Songreload.pulse() # type: ignore