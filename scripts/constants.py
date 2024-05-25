from enums import SongCodec

HEADERS = {
  'Content-Type': 'application/json;charset=utf-8',
  'Connection': 'keep-alive',
  'Accept': 'application/json',
  'Origin': 'https://music.apple.com',
  'Referer': 'https://music.apple.com/',
  'Accept-Encoding': 'gzip, deflate, br',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,like Gecko) Chrome/110.0.0.0 Safari/537.36'
}

SONG_CODEC_REGEX_MAP = {
    SongCodec.AAC: r"audio-stereo-\d+",
    SongCodec.AAC_HE: r"audio-HE-stereo-\d+",
    SongCodec.AAC_BINAURAL: r"audio-stereo-\d+-binaural",
    SongCodec.AAC_DOWNMIX: r"audio-stereo-\d+-downmix",
    SongCodec.AAC_HE_BINAURAL: r"audio-HE-stereo-\d+-binaural",
    SongCodec.AAC_HE_DOWNMIX: r"audio-HE-stereo-\d+-downmix",
    SongCodec.ATMOS: r"audio-atmos-.*",
    SongCodec.AC3: r"audio-ac3-.*",
    SongCodec.ALAC: r"audio-alac-.*",
}

URL = {
  "WEBPLAYBACK": "https://play.itunes.apple.com/WebObjects/MZPlay.woa/wa/webPlayback",
  "SONG_INFO_BASE": "https://amp-api.music.apple.com/v1/catalog/",
  "LICENSE_API": "https://play.itunes.apple.com/WebObjects/MZPlay.woa/wa/acquireWebPlaybackLicense"
}

MP4_TAGS_MAP = {
    "album": "\xa9alb",
    "album_artist": "aART",
    "album_id": "plID",
    "album_sort": "soal",
    "artist": "\xa9ART",
    "artist_id": "atID",
    "artist_sort": "soar",
    "comment": "\xa9cmt",
    "composer": "\xa9wrt",
    "composer_id": "cmID",
    "composer_sort": "soco",
    "copyright": "cprt",
    "date": "\xa9day",
    "genre": "\xa9gen",
    "genre_id": "geID",
    "lyrics": "\xa9lyr",
    "media_type": "stik",
    "rating": "rtng",
    "storefront": "sfID",
    "title": "\xa9nam",
    "title_id": "cnID",
    "title_sort": "sonm",
    "xid": "xid",
}