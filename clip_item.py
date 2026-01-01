from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsDropShadowEffect
from PyQt5.QtGui import QBrush, QColor, QPen, QFont, QLinearGradient, QPixmap
from PyQt5.QtCore import Qt, QRectF, QPointF
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
        self.setPos(self.start * scale, self.track * 40 + 35)
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
        self.drag_mode = None

    def paint(self, painter, option, widget):
        rect = self.rect()
        painter.setClipRect(rect)
        grad = QLinearGradient(0, 0, 0, rect.height())
        if self.isSelected():
            grad.setColorAt(0, QColor(70, 130, 180))
            grad.setColorAt(1, QColor(50, 100, 150))
        else:
            grad.setColorAt(0, QColor(50, 50, 50))
            grad.setColorAt(1, QColor(30, 30, 30))
        painter.setBrush(QBrush(grad))
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 215, 0), 2))
        else:
            painter.setPen(QPen(QColor(10, 10, 10), 1))
        painter.drawRoundedRect(rect, 4, 4)
        if self.model.width > 0 and self.thumbnail_start:
            thumb_h = rect.height()
            thumb_w = int(self.thumbnail_start.width() * (thumb_h / self.thumbnail_start.height()))
            current_x = 0
            while current_x < rect.width():
                target = QRectF(current_x, 0, thumb_w, thumb_h)
                pm = self.thumbnail_start
                if self.thumbnail_end and (int(current_x / thumb_w) % 2 == 1):
                    pm = self.thumbnail_end
                painter.setOpacity(1.0)
                painter.drawPixmap(target, pm, QRectF(pm.rect()))
                current_x += thumb_w
        if self.waveform_pixmap:
            painter.setOpacity(0.8)
            painter.drawPixmap(rect.toRect(), self.waveform_pixmap)
        fi_w = self.model.fade_in * self.scale
        if fi_w > 0:
            grad = QLinearGradient(0, 0, fi_w, 0)
            grad.setColorAt(0, QColor(0, 0, 0, 200))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(QRectF(0, 0, fi_w, rect.height()), grad)
        fo_w = self.model.fade_out * self.scale
        if fo_w > 0:
            x_start = rect.width() - fo_w
            grad = QLinearGradient(x_start, 0, rect.width(), 0)
            grad.setColorAt(0, QColor(0, 0, 0, 0))
            grad.setColorAt(1, QColor(0, 0, 0, 200))
            painter.fillRect(QRectF(x_start, 0, fo_w, rect.height()), grad)
        painter.setPen(QPen(Qt.white, 1))
        painter.setBrush(Qt.white)
        painter.drawEllipse(QPointF(fi_w, 6), 4, 4)
        painter.drawEllipse(QPointF(rect.width() - fo_w, 6), 4, 4)
        painter.setOpacity(1.0)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(int(fi_w) + 8, 15, self.name)
        if self.scene():
            my_scene_rect = self.sceneBoundingRect()
            i_am_video = self.model.width > 0
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.setPen(Qt.NoPen)
            for item in self.scene().items():
                if isinstance(item, ClipItem) and item != self and item.track > self.track:
                    them_video = item.model.width > 0
                    if i_am_video != them_video: continue 
                    other_rect = item.sceneBoundingRect()
                    intersect = my_scene_rect.intersected(other_rect)
                    if not intersect.isEmpty():
                        local_intersect = self.mapFromScene(intersect).boundingRect()
                        painter.drawRect(local_intersect)

    def mousePressEvent(self, event):
        pos = event.pos()
        fi_x = self.model.fade_in * self.scale
        fo_x = self.rect().width() - (self.model.fade_out * self.scale)
        if abs(pos.x() - fi_x) < 10 and abs(pos.y() - 6) < 10:
            self.drag_mode = 'fade_in'
            event.accept()
        elif abs(pos.x() - fo_x) < 10 and abs(pos.y() - 6) < 10:
            self.drag_mode = 'fade_out'
            event.accept()
        else:
            self.drag_mode = 'move'
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_mode == 'fade_in':
            x = max(0, event.pos().x())
            val = x / self.scale
            self.model.fade_in = min(val, self.model.duration / 2)
            self.update()
        elif self.drag_mode == 'fade_out':
            x = min(self.rect().width(), event.pos().x())
            val = (self.rect().width() - x) / self.scale
            self.model.fade_out = min(val, self.model.duration / 2)
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_mode in ['fade_in', 'fade_out']:
            self.drag_mode = None
        else:
            super().mouseReleaseEvent(event)
            
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            track_h = 40
            t_idx = round((new_pos.y() - 35) / track_h)
            t_idx = max(0, t_idx)
            tentative_y = t_idx * track_h + 35
            future_rect = QRectF(new_pos.x(), tentative_y, self.rect().width(), self.rect().height())
            new_pos.setY(tentative_y)
            self.track = t_idx
            view = self.scene().views()[0]
            snapped_x = view.get_snapped_x(new_pos.x())
            new_pos.setX(max(0, snapped_x))
            return new_pos
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.start = self.x() / self.scale
        self.model.start = self.start
        self.model.track = self.track
        if self.scene():
            collisions = [i for i in self.scene().items() 
                          if isinstance(i, ClipItem) and i != self and i.track == self.track and i.collidesWithItem(self)]
            if collisions:
                victim = min(collisions, key=lambda x: x.start)
                required_clearance = self.start + self.duration
                offset = required_clearance - victim.start
                if offset > 0:
                    items_to_shift = [i for i in self.scene().items() 
                                      if isinstance(i, ClipItem) and i != self and i.track == self.track and i.start >= victim.start]
                    for item in items_to_shift:
                        item.start += offset
                        item.model.start = item.start
                        item.setX(item.start * item.scale)
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            if view.snap_line:
                view.scene.removeItem(view.snap_line)
                view.snap_line = None
            view.fit_to_view()

    def set_speed(self, value):
        self.model.speed = value
        self.speed = value

    def set_volume(self, value):
        self.model.volume = value
        self.volume = value
