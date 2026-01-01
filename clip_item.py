from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsTextItem, QGraphicsDropShadowEffect
from PyQt5.QtGui import QBrush, QColor, QPen, QFont, QLinearGradient
from PyQt5.QtCore import Qt, QRectF

from model import ClipModel

class ClipItem(QGraphicsRectItem):
    def __init__(self, model: ClipModel, scale=50):
        super().__init__(0, 0, model.duration * scale, 30)
        self.model = model
        self.uid = model.uid
        self.name = model.name
        self.start = model.start
        self.duration = model.duration
        self.track = model.track
        self.speed = model.speed
        self.volume = model.volume
        self.scale = scale
        self.setPos(self.start * scale, self.track * 40 + 5)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(5)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)
        self.waveform_pixmap = None
        self.thumbnail_start = None
        self.thumbnail_end = None

    def paint(self, painter, option, widget):
        if self.waveform_pixmap:
            brush = QBrush(self.waveform_pixmap.scaled(
                int(self.rect().width()), int(self.rect().height()),
                Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            painter.setBrush(brush)
        else:
            grad = QLinearGradient(0, 0, 0, self.rect().height())
            if self.isSelected():
                grad.setColorAt(0, QColor(70, 130, 180))
                grad.setColorAt(1, QColor(50, 100, 150))
            else:
                grad.setColorAt(0, QColor(60, 60, 60))
                grad.setColorAt(1, QColor(40, 40, 40))
            painter.setBrush(QBrush(grad))

        if self.isSelected():
            painter.setPen(QPen(QColor(255, 255, 0), 2))
        else:
            painter.setPen(QPen(QColor(20, 20, 20), 1))

        painter.drawRoundedRect(self.rect(), 6, 6)
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawLine(0, 0, int(self.rect().width()), 0)

        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(5, 15, self.name)

        painter.setOpacity(0.5)
        thumb_h = self.rect().height()
        if self.thumbnail_start:
            thumb_w = int(self.thumbnail_start.width() * (thumb_h / self.thumbnail_start.height()))
            thumb_rect = QRectF(0, 0, thumb_w, thumb_h)
            painter.drawPixmap(thumb_rect, self.thumbnail_start, QRectF(self.thumbnail_start.rect()))

        if self.thumbnail_end:
            thumb_w = int(self.thumbnail_end.width() * (thumb_h / self.thumbnail_end.height()))
            thumb_rect = QRectF(self.rect().width() - thumb_w, 0, thumb_w, thumb_h)
            painter.drawPixmap(thumb_rect, self.thumbnail_end, QRectF(self.thumbnail_end.rect()))
        painter.setOpacity(1.0)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            track_h = 40
            t_idx = round((new_pos.y() - 5) / track_h)
            t_idx = max(0, t_idx)
            new_pos.setY(t_idx * track_h + 5)
            self.track = t_idx
            view = self.scene().views()[0]
            snapped_x = view.get_snapped_x(new_pos.x())
            new_pos.setX(max(0, snapped_x))
            return new_pos
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.start = self.x() / self.scale
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            if view.snap_line:
                view.scene.removeItem(view.snap_line)
                view.snap_line = None

    def set_speed(self, value):
        self.model.speed = value
        self.speed = value

    def set_volume(self, value):
        self.model.volume = value
        self.volume = value
