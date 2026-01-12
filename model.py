from dataclasses import dataclass, field, fields, asdict
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
    media_type: str = 'video'
    has_audio: bool = True
    linked_uid: str = None
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_freeze: float = 0.0
    end_freeze: float = 0.0
    is_main_audio_source: bool = False
    @classmethod

    def from_dict(cls, data):
        if 'dur' in data and 'duration' not in data:
            data = data.copy()
            data['duration'] = data['dur']
        valid_keys = {f.name for f in fields(cls)}
        filtered_args = {k: v for k, v in data.items() if k in valid_keys}
        required_defaults = {'path': "MISSING_PATH", 'track': 0, 'start': 0.0, 'duration': 5.0}
        for key, default in required_defaults.items():
            if key not in filtered_args:
                filtered_args[key] = default
        return cls(**filtered_args)

    def to_dict(self):
        data = asdict(self)
        data['dur'] = self.duration
        return data