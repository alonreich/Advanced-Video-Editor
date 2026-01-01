from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QScrollBar, QToolTip
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QPoint, QLineF, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QDrag, QLinearGradient, QGradient
import os
import uuid
from clip_item import ClipItem

class TimelineScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, 3600*50, 600)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        r = self.sceneRect()
        left = int(rect.left())
        right = int(rect.right())
        painter.setPen(QPen(QColor(45, 45, 45), 1))
        for i in range(10):
            y = i * 100
            if i % 2 == 0:
                painter.fillRect(left, y, right - left, 100, QColor(35, 35, 35))
            else:
                painter.fillRect(left, y, right - left, 100, QColor(40, 40, 40))
            painter.drawLine(left, y, right, y)
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        start_sec = int(left / 50)
        end_sec = int(right / 50)
        for sec in range(start_sec, end_sec + 1):
            x = sec * 50
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))

class TimelineView(QGraphicsView):
    clip_selected = pyqtSignal(dict)
    time_updated = pyqtSignal(float)
    file_dropped = pyqtSignal(str, int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = TimelineScene()
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.scale_factor = 50
        self.playhead_pos = 0.0
        self.scene.selectionChanged.connect(self.on_selection_change)
        self.ruler_height = 30
        self.track_height = 100

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, max(3600*50, self.width()), 10 * 100)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        ruler_rect = QRectF(rect.left(), rect.top(), rect.width(), self.ruler_height)
        painter.fillRect(ruler_rect, QColor(25, 25, 25))
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawLine(int(rect.left()), int(rect.top() + self.ruler_height), int(rect.right()), int(rect.top() + self.ruler_height))
        start_x = rect.left()
        end_x = rect.right()
        start_sec = int(start_x / self.scale_factor)
        end_sec = int(end_x / self.scale_factor)
        for sec in range(start_sec, end_sec + 1):
            x = sec * self.scale_factor
            if x < start_x: continue
            tick_h = 15 if sec % 5 == 0 else 8
            painter.drawLine(int(x), int(rect.top() + self.ruler_height - tick_h), int(x), int(rect.top() + self.ruler_height))
            if sec % 5 == 0:
                mins = sec // 60
                secs = sec % 60
                ts = f"{mins:02}:{secs:02}"
                painter.drawText(int(x) + 2, int(rect.top() + 12), ts)
        px = self.playhead_pos * self.scale_factor
        if px >= rect.left() and px <= rect.right():
            painter.setPen(QPen(QColor(255, 0, 0), 1))
            painter.drawLine(int(px), int(rect.top()), int(px), int(rect.bottom()))
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            painter.drawPolygon(
                QPoint(int(px) - 5, int(rect.top())), 
                QPoint(int(px) + 5, int(rect.top())), 
                QPoint(int(px), int(rect.top()) + 10)
            )

    def mousePressEvent(self, event):
        if event.pos().y() < self.ruler_height:
            pt = self.mapToScene(event.pos())
            self.user_set_playhead(pt.x())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and event.pos().y() < self.ruler_height:
            pt = self.mapToScene(event.pos())
            self.user_set_playhead(pt.x())
        super().mouseMoveEvent(event)

    def user_set_playhead(self, x):
        sec = max(0, x / self.scale_factor)
        self.playhead_pos = sec
        self.scene.update()
        self.time_updated.emit(sec)
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            pt = self.mapToScene(event.pos())
            track_idx = int(pt.y() // self.track_height)
            snapped_x = self.get_snapped_x(pt.x())
            time_pos = max(0, snapped_x / self.scale_factor)
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    self.file_dropped.emit(path, track_idx, time_pos)
            event.accept()
        else:
            super().dropEvent(event)

    def get_snapped_x(self, x_pos, threshold=15):
        snaps = [0, self.playhead_pos * self.scale_factor]
        for item in self.scene.items():
            if isinstance(item, ClipItem) and not item.isSelected():
                snaps.append(item.x())
                snaps.append(item.x() + item.rect().width())
        closest = x_pos
        min_dist = threshold + 1
        for s in snaps:
            dist = abs(x_pos - s)
            if dist < min_dist:
                min_dist = dist
                closest = s
        return closest if min_dist <= threshold else x_pos

    from model import ClipModel

    def add_clip(self, clip_data):
        if isinstance(clip_data, dict):
            model = ClipModel.from_dict(clip_data)
        elif isinstance(clip_data, ClipModel):
            model = clip_data
        else:
            model = ClipModel.from_dict(clip_data)
        item = ClipItem(model, self.scale_factor)
        self.scene.addItem(item)

    def set_time(self, seconds):
        self.playhead_pos = seconds
        self.scene.update()
        px = seconds * self.scale_factor
        vp_left = self.horizontalScrollBar().value()
        vp_width = self.viewport().width()
        if px > vp_left + vp_width - 50:
            self.horizontalScrollBar().setValue(int(px - 100))
        elif px < vp_left:
            self.horizontalScrollBar().setValue(int(px - 100))

    def on_selection_change(self):
        sel = self.scene.selectedItems()
        if sel and isinstance(sel[0], ClipItem):
            self.clip_selected.emit(sel[0])
        else:
            self.clip_selected.emit(None)

    def get_state(self):
        st = []
        for item in self.scene.items():
            if isinstance(item, ClipItem):
                st.append({
                    'uid': item.uid,
                    'name': item.name,
                    'path': item.name,
                    'start': item.start,
                    'dur': item.duration,
                    'track': item.track,
                    'speed': getattr(item, 'speed', 1.0)
                })
        return st

    def load_state(self, state):
        self.scene.clear()
        for c in state:
            if 'name' not in c and 'path' in c:
                c['name'] = os.path.basename(c['path'])
            elif 'name' not in c:
                c['name'] = "Untitled"
            c.setdefault('uid', str(uuid.uuid4()))
            c.setdefault('start', 0.0)
            c.setdefault('dur', 5.0)
            c.setdefault('track', 0)
            self.add_clip(c)

    def get_selected_item(self):
        sel = self.scene.selectedItems()
        return sel[0] if sel else None

    def remove_selected_clips(self):
        for item in self.scene.selectedItems():
            self.scene.removeItem(item)
