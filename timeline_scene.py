from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtGui import QBrush, QColor, QPen
import constants

class TimelineScene(QGraphicsScene):

    def __init__(self, num_tracks=6, track_height=constants.TRACK_HEIGHT):
        super().__init__()
        self.num_tracks = num_tracks
        self.track_height = track_height
        self.setSceneRect(0, 0, 3600*constants.DEFAULT_TIMELINE_SCALE_FACTOR, (self.num_tracks * self.track_height) + constants.RULER_HEIGHT)
        self.setBackgroundBrush(QBrush(QColor(constants.COLOR_BACKGROUND)))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        left = int(rect.left())
        right = int(rect.right())
        for i in range(self.num_tracks):
            y = i * self.track_height + constants.RULER_HEIGHT
            color = QColor(35, 35, 35) if i % 2 == 0 else QColor(40, 40, 40)
            painter.fillRect(left, y, right - left, self.track_height, color)
            painter.setPen(QPen(QColor(45, 45, 45), 1))
            painter.drawLine(left, y, right, y)
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        start_sec = int(left / constants.DEFAULT_TIMELINE_SCALE_FACTOR)
        end_sec = int(right / constants.DEFAULT_TIMELINE_SCALE_FACTOR)
        scale = getattr(self.parent(), 'scale_factor', constants.DEFAULT_TIMELINE_SCALE_FACTOR)
        for sec in range(start_sec, end_sec + 1):
            x = sec * scale
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))