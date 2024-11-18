from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import ssl

def check_url(url) -> bool:
  try:
    __url = urlparse(url)   
    if not __url.scheme:
      url = 'https://' + url
    
    if __url.netloc == "music.apple.com":
      print(url)
      context = ssl._create_unverified_context() # running td on macos require
      urlopen(url, context=context)
      return True
    else:
      return False

  except (URLError, HTTPError):
    print('Not Apple Music URL :/')
    return False
  
def get_url_info(url) -> dict:
  if check_url(url):
    splits = url.split('/')
    track_id = splits[-1]
    kind = splits[4]
    
    if kind == 'album':
      if len(track_id.split('?i=')) > 1:
        track_id = track_id.split('?i=')[1]
        track_id = track_id.split('&')[0]
        kind = 'songs'
    
    return {
      'kind': kind,
      'track_id': track_id
    }
  else:
    print('Albums not supported yet...')
    return {
      'kind': None,
      'track_id': None
    }