from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

def check_url(url) -> bool:
  try:
    __url = urlparse(url)   
    if not __url.scheme:
      url = 'https://' + url
    
    if __url.netloc == "music.apple.com":
      urlopen(url)
      return True
    else:
      return False
    
  except (URLError, HTTPError):
    return False
  
def get_url_info(url) -> dict:
  if check_url(url):
    splits = url.split('/')
    track_id = splits[-1]
    kind = splits[4]
    
    if kind == 'album':
      if len(track_id.split('?i=')) > 1:
        track_id = track_id.split('?i=')[1]
        kind = 'songs'
    
    return {
      'kind': kind,
      'track_id': track_id
    }
  else:
    return {
      'kind': None,
      'track_id': None
    }