import re
import requests
import json

from constants import HEADERS, URL
from checker import get_url_info

class AppleMusicAPI:
  def __init__(self, user_token: str):
    self.session = requests.Session()
    self.session.headers.update(HEADERS)
    self._MUT = user_token

    self.__setMUT()

    self.__acessToken()
    self.__mediaUserToken()

  def __setMUT(self) -> None:
    self.MUT = self._MUT

  def __acessToken(self) -> None:
    response = requests.get('https://music.apple.com/us/browse')
    if response.status_code != 200:
      raise Exception('Error while loading main page: ' + str(response.status_code))
  
    indexJs = re.search('(?<=index)(.*?)(?=\.js")', response.text).group(1)
    response = self.session.get('https://music.apple.com/assets/index' + indexJs + '.js')
    if response.status_code != 200:
      print('Error getting index: ' + str(response.status_code)) # type: ignore
  
    accessToken = re.search('(?=eyJh)(.*?)(?=")', response.text).group(1)
    self.session.headers.update({'Authorization': 'Bearer ' + accessToken})
    print('Access Token OK')

  def __mediaUserToken(self) -> None:
    self.session.headers.update({'media-user-token': self.MUT})
    response = self.session.get('https://amp-api.music.apple.com/v1/me/storefront')
    if response.status_code == 200:
      response = json.loads(response.text)
      self.storefront = response["data"][0].get("id")
      self.language = response["data"][0]["attributes"].get("defaultLanguageTag")
      self.session.headers.update({'media-user-token': self.MUT})
      print('Media User Token OK')
    else:
      print('Error getting MUT: ' + str(response.status_code)) # type: ignore

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
          print('Song Info OK')
          return response.json()['data'][0]
        else:
          raise Exception(str(response.status_code))
        
      except Exception as e:
        print('Error getting song info: ' + str(e))
        print('Song Info ERROR')
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
      print('Web Playback OK')
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
