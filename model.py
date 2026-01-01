from dataclasses import dataclass, field
import uuid
@dataclass
class ClipModel:
    path: str
    track: int
    start: float
    duration: float
    source_in: float = 0.0
    speed: float = 1.0
    volume: float = 100.0
    name: str = "Untitled"
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self):
        return {
            'uid': self.uid, 'path': self.path, 'name': self.name,
            'track': self.track, 'start': self.start, 'dur': self.duration,
            'source_in': self.source_in, 'speed': self.speed, 'volume': self.volume
        }
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
        return m
