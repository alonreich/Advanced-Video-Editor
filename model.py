from dataclasses import dataclass, field
import uuid
@dataclass
class ClipModel:
    path: str
    track: int
    start: float
    duration: float
    source_in: float = 0.0
    source_duration: float = 0.0
    speed: float = 1.0
    volume: float = 100.0
    name: str = "Untitled"
    scale_x: float = 1.0
    scale_y: float = 1.0
    pos_x: float = 0.0
    pos_y: float = 0.0
    width: int = 1920
    height: int = 1080
    bitrate: int = 0
    crop_x1: float = 0.0
    crop_y1: float = 0.0
    crop_x2: float = 1.0
    crop_y2: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))

    @staticmethod
    def from_dict(data):
        m = ClipModel(
            path=data.get('path', ''),
            track=data.get('track', 0),
            start=data.get('start', 0.0),
            duration=data.get('dur', 5.0),
            name=data.get('name', 'Untitled'),
            uid=data.get('uid', str(uuid.uuid4()))
        )
        m.source_in = data.get('source_in', 0.0)
        m.source_duration = data.get('source_duration', m.duration) # Fallback to clip dur if missing
        m.speed = data.get('speed', 1.0)
        m.volume = data.get('volume', 100.0)
        m.scale_x = data.get('scale_x', 1.0)
        m.scale_y = data.get('scale_y', 1.0)
        m.pos_x = data.get('pos_x', 0.0)
        m.pos_y = data.get('pos_y', 0.0)
        m.width = data.get('width', 1920)
        m.height = data.get('height', 1080)
        m.bitrate = data.get('bitrate', 0)
        m.crop_x1 = data.get('crop_x1', 0.0)
        m.crop_y1 = data.get('crop_y1', 0.0)
        m.crop_x2 = data.get('crop_x2', 1.0)
        m.crop_y2 = data.get('crop_y2', 1.0)
        m.fade_in = data.get('fade_in', 0.0)
        m.fade_out = data.get('fade_out', 0.0)
        return m
    @staticmethod
    def from_dict(data):
        m = ClipModel(
            path=data.get('path', ''),
            track=data.get('track', 0),
            start=data.get('start', 0.0),
            duration=data.get('dur', 5.0),
            name=data.get('name', 'Untitled'),
            uid=data.get('uid', str(uuid.uuid4()))
        )
        m.source_in = data.get('source_in', 0.0)
        m.speed = data.get('speed', 1.0)
        m.volume = data.get('volume', 100.0)
        m.scale_x = data.get('scale_x', 1.0)
        m.scale_y = data.get('scale_y', 1.0)
        m.pos_x = data.get('pos_x', 0.0)
        m.pos_y = data.get('pos_y', 0.0)
        m.width = data.get('width', 1920)
        m.height = data.get('height', 1080)
        m.bitrate = data.get('bitrate', 0)
        m.crop_x1 = data.get('crop_x1', 0.0)
        m.crop_y1 = data.get('crop_y1', 0.0)
        m.crop_x2 = data.get('crop_x2', 1.0)
        m.crop_y2 = data.get('crop_y2', 1.0)
        m.fade_in = data.get('fade_in', 0.0)
        m.fade_out = data.get('fade_out', 0.0)
        return m
