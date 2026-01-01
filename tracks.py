from PyQt5.QtWidgets import QFrame
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag, QPainter, QColor
import uuid
class ClipObj:
    def __init__(self, path, start, dur):
        self.uid = str(uuid.uuid4())
        self.path = path
        self.start = start
        self.dur = dur
        self.lane = 0
class TrackWidget(QFrame):
    def __init__(self, idx, timeline):
        super().__init__()
        self.idx = idx
        self.timeline = timeline
        self.clips = []
        self.setFixedHeight(100)
        self.setAcceptDrops(True)
        self.setStyleSheet("background: #2b2b2b; border-bottom: 1px solid #444;")
    def add_clip(self, path, start, dur=10.0):
        c = ClipObj(path, start, dur)
        self.clips.append(c)
        self.update()
    def paintEvent(self, e):
        p = QPainter(self)
        scale = 50
        for c in self.clips:
            x = int(c.start * scale)
            w = int(c.dur * scale)
            p.fillRect(x, 10, w, 80, QColor("#3a86ff"))
            p.setPen(Qt.white)
            p.drawText(x+5, 30, c.path)
    def get_state(self):
        return [{'path':c.path, 'start':c.start, 'dur':c.dur} for c in self.clips]
