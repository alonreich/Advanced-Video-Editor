from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtGui import QBrush, QColor, QPen

class TimelineScene(QGraphicsScene):
    def __init__(self, num_tracks=6, track_height=0):
        super().__init__()
        self.num_tracks = num_tracks
        self.track_height = track_height
        self.setSceneRect(0, 0, 3600*40, self.num_tracks * self.track_height)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        left = int(rect.left())
        right = int(rect.right())
        for i in range(self.num_tracks):
            y = i * self.track_height + 30
            color = QColor(35, 35, 35) if i % 2 == 0 else QColor(40, 40, 40)
            painter.fillRect(left, y, right - left, self.track_height, color)
            painter.setPen(QPen(QColor(45, 45, 45), 1))
            painter.drawLine(left, y, right, y)
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        start_sec = int(left / 50)
        end_sec = int(right / 50)
        for sec in range(start_sec, end_sec + 1):
            x = sec * 50
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
