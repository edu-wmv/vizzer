import m3u8
import base64
import subprocess
from pathlib import Path
from pywidevine import PSSH
from pywidevine.license_protocol_pb2 import WidevinePsshData
from enums import SongCodec
from models import StreamInfo
from downloader import Downloader

class DownloaderSongLegacy:
  def __init__(self, codec, token):
    self.codec = codec
    self.token = token
    self.downloader = Downloader(self.token)
    
  def getStreamInfo(self, webplayback: dict) -> StreamInfo:
    try:
      flavor = "32:ctrp64" if self.codec == SongCodec.AAC_HE_LEGACY else "28:ctrp256"
      stream_info = StreamInfo()
      stream_info.stream_url = next(
        x 
        for x in webplayback["assets"] 
        if x["flavor"] == flavor
      )["URL"]

      m3u8_obj = m3u8.load(uri=stream_info.stream_url, verify_ssl=False)
      stream_info.pssh = m3u8_obj.keys[0].uri
      stream_info.codec = self.codec

      if (
        stream_info.stream_url != None and 
        stream_info.pssh != None
      ):
        print('Stream Info OK OK')
        return stream_info
      else:
        raise Exception('Error getting stream info')
    except Exception as e:
      print('Stream Info ERROR ERROR: ' + str(e))
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
    
      print('Decryption Key OK')
      
    except Exception as e:
      print('Decryption Key ERROR: ' + str(e))
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
    
    print('Remux OK')
