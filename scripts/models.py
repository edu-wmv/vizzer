from dataclasses import dataclass

@dataclass
class StreamInfo:
  stream_url: str = None
  pssh: str = None
  codec: str = None
