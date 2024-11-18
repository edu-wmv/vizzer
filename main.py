import json

from legacy_download import DownloaderSongLegacy
from enums import SongCodec
from song import Song

token = parent().par.Usermediatoken.eval() # type: ignore
url = parent().par.Url.eval() # type: ignore


if not token:
  op('/project1/out_text').text = 'Media User Token not found' # type: ignore
  raise Exception('Media User Token not found')
if not url:
  op('/project1/out_text').text = 'URL not found' # type: ignore
  raise Exception('URL not found')
 
try:
  codec = SongCodec.AAC_LEGACY
  legacy = DownloaderSongLegacy(codec, token)

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

except Exception as e:
  print('Error: ' + str(e))
  op('/project1/out_text').text = 'Error: ' + str(e) # type: ignore

op('request_output').text = json.dumps(song_json) # type: ignore
op('/project1/creep1').par.reset.pulse() # type: ignore
parent().par.Songreload.pulse() # type: ignore