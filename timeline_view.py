from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QScrollBar, QToolTip
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QPoint, QLineF, QTimer, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QDrag, QLinearGradient, QGradient, QPolygonF
import os
import uuid
from enum import Enum
from clip_item import ClipItem
from model import ClipModel


class Mode(Enum):
    POINTER = 1
    RAZOR = 2


class TimelineScene(QGraphicsScene):
    def __init__(self, num_tracks=3, track_height=50):
        super().__init__()
        self.num_tracks = num_tracks
        self.track_height = track_height
        self.setSceneRect(0, 0, 3600*50, self.num_tracks * self.track_height)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        r = self.sceneRect()
        left = int(rect.left())
        right = int(rect.right())
        painter.setPen(QPen(QColor(45, 45, 45), 1))
        for i in range(self.num_tracks):
            y = i * self.track_height
            if i % 2 == 0:
                painter.fillRect(left, y, right - left, self.track_height, QColor(35, 35, 35))
            else:
                painter.fillRect(left, y, right - left, self.track_height, QColor(40, 40, 40))
            painter.drawLine(left, y, right, y)
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        start_sec = int(left / 50)
        end_sec = int(right / 50)
        for sec in range(start_sec, end_sec + 1):
            x = sec * 50
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))

class TimelineView(QGraphicsView):
    clip_selected = pyqtSignal(object)
    time_updated = pyqtSignal(float)
    file_dropped = pyqtSignal(str, int, float)
    clip_split_requested = pyqtSignal(object, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = Mode.POINTER
        self.num_tracks = 3
        self.track_height = 40
        self.scene = TimelineScene(self.num_tracks, self.track_height)
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.scale_factor = 50
        self.playhead_pos = 0.0
        self.scene.selectionChanged.connect(self.on_selection_change)
        self.ruler_height = 30
        self.is_dragging_playhead = False
        self.snap_line = None

    def add_track_to_scene(self):
        self.num_tracks += 1
        self.scene.num_tracks = self.num_tracks
        self.scene.setSceneRect(0, 0, self.scene.sceneRect().width(), self.num_tracks * self.track_height)
        self.scene.update()

    def set_mode(self, mode):
        self.mode = mode

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, max(3600*50, self.width()), self.num_tracks * self.track_height)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        
        # Ruler background
        ruler_rect = QRectF(rect.left(), 0, rect.width(), self.ruler_height)
        painter.fillRect(ruler_rect, QColor(25, 25, 25))
        
        # Ruler line
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawLine(int(rect.left()), self.ruler_height, int(rect.right()), self.ruler_height)

        # Ruler ticks and numbers
        start_x = rect.left()
        end_x = rect.right()
        
        start_scene_x = self.mapToScene(QPoint(int(start_x), 0)).x()
        end_scene_x = self.mapToScene(QPoint(int(end_x), 0)).x()

        start_sec = int(start_scene_x / self.scale_factor)
        end_sec = int(end_scene_x / self.scale_factor)

        for sec in range(start_sec, end_sec + 1):
            scene_x = sec * self.scale_factor
            vp_x = self.mapFromScene(QPointF(scene_x, 0)).x()
            
            if vp_x < start_x or vp_x > end_x: continue
            
            tick_h = 15 if sec % 5 == 0 else 8
            painter.drawLine(int(vp_x), self.ruler_height - tick_h, int(vp_x), self.ruler_height)
            
            if sec % 5 == 0:
                mins = sec // 60
                secs = sec % 60
                ts = f"{mins:02}:{secs:02}"
                painter.drawText(int(vp_x) + 2, 12, ts)

        # Playhead
        playhead_scene_x = self.playhead_pos * self.scale_factor
        playhead_vp_x = self.mapFromScene(QPointF(playhead_scene_x, 0)).x()

        if playhead_vp_x >= rect.left() and playhead_vp_x <= rect.right():
            painter.setPen(QPen(QColor(255, 0, 0), 1))
            painter.drawLine(int(playhead_vp_x), 0, int(playhead_vp_x), int(rect.height()))
            
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            poly = QPolygonF([
                QPointF(playhead_vp_x - 7, 0),
                QPointF(playhead_vp_x + 7, 0),
                QPointF(playhead_vp_x, 15)
            ])
            painter.drawPolygon(poly)

    def mousePressEvent(self, event):
        if self.mode == Mode.RAZOR:
            if event.button() == Qt.LeftButton:
                item = self.itemAt(event.pos())
                if isinstance(item, ClipItem):
                    pt = self.mapToScene(event.pos())
                    split_time = pt.x() / self.scale_factor
                    self.clip_split_requested.emit(item, split_time)
            return

        if event.button() == Qt.LeftButton:
            px_scene = self.playhead_pos * self.scale_factor
            px_viewport = self.mapFromScene(QPointF(px_scene, 0)).x()
            handle_rect = QRectF(px_viewport - 7, 0, 14, 15)

            if handle_rect.contains(event.pos()):
                self.is_dragging_playhead = True
                pt = self.mapToScene(event.pos())
                self.user_set_playhead(pt.x())
            elif event.pos().y() < self.ruler_height:
                pt = self.mapToScene(event.pos())
                self.user_set_playhead(pt.x())
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.is_dragging_playhead:
            pt = self.mapToScene(event.pos())
            self.user_set_playhead(pt.x())
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging_playhead = False
        super().mouseReleaseEvent(event)

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
            
            # Check if track is empty
            track_is_empty = True
            for item in self.scene.items():
                if isinstance(item, ClipItem) and item.track == track_idx:
                    track_is_empty = False
                    break
            
            time_pos = 0.0 # Default to beginning
            if not track_is_empty:
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
        
        closest_snap = None
        min_dist = float('inf')

        for s in snaps:
            dist = abs(x_pos - s)
            if dist < min_dist:
                min_dist = dist
                closest_snap = s

        if self.snap_line:
            self.scene.removeItem(self.snap_line)
            self.snap_line = None

        if min_dist <= threshold:
            pen = QPen(Qt.cyan, 1)
            self.snap_line = self.scene.addLine(closest_snap, 0, closest_snap, self.scene.height(), pen)
            return closest_snap
        else:
            return x_pos

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

    def reorder_tracks(self, source_idx, target_idx):
        self.scene.blockSignals(True)
        
        items_on_source = [item for item in self.scene.items() if isinstance(item, ClipItem) and item.track == source_idx]
        
        if source_idx < target_idx:
            for i in range(source_idx + 1, target_idx + 1):
                items_on_track = [item for item in self.scene.items() if isinstance(item, ClipItem) and item.track == i]
                for item in items_on_track:
                    item.track -= 1
                    item.model.track -= 1
                    item.setY(item.y() - self.track_height)
        else:
            for i in range(target_idx, source_idx):
                items_on_track = [item for item in self.scene.items() if isinstance(item, ClipItem) and item.track == i]
                for item in items_on_track:
                    item.track += 1
                    item.model.track += 1
                    item.setY(item.y() + self.track_height)

        for item in items_on_source:
            item.track = target_idx
            item.model.track = target_idx
            item.setY(target_idx * self.track_height + 5)
            
        self.scene.blockSignals(False)