from bs4 import BeautifulSoup
from Pylette import extract_colors

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
    palette = extract_colors(image=cover_path, palette_size=4, resize=True)
    print('Palette: ', palette)
    cols = []
    # cols = ["100", "100", "100"]
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
    
    print('Data Fix OK')
    return info
 