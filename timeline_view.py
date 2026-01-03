from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QScrollBar, QToolTip, QMenu
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

class TimelineView(QGraphicsView):
    clip_selected = pyqtSignal(object)
    time_updated = pyqtSignal(float)
    file_dropped = pyqtSignal(str, int, float)
    clip_split_requested = pyqtSignal(object, float)
    seek_request = pyqtSignal(float)
    data_changed = pyqtSignal()
    interaction_started = pyqtSignal()
    interaction_ended = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        import logging
        self.logger = logging.getLogger("Advanced_Video_Editor")
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
        self.snapping_enabled = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            delta = -5.0 if event.modifiers() & Qt.ShiftModifier else -0.1
            self.seek_request.emit(delta)
            event.accept()
        elif event.key() == Qt.Key_Right:
            delta = 5.0 if event.modifiers() & Qt.ShiftModifier else 0.1
            self.seek_request.emit(delta)
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.scale_factor *= 1.1
            else:
                self.scale_factor *= 0.9
            self.scale_factor = max(1, min(self.scale_factor, 500))
            for item in self.scene.items():
                if isinstance(item, ClipItem):
                    item.scale = self.scale_factor
                    item.setPos(item.model.start * self.scale_factor, item.y())
                    item.setRect(0, 0, item.model.duration * self.scale_factor, 30)
            self.scene.update()
            event.accept()
        else:
            super().wheelEvent(event)

    def split_audio_video(self, clip_item):
        """Separates the audio stream into a new clip on the track below."""
        self.logger.info(f"Splitting audio for clip {clip_item.name}")
        new_audio_model = ClipModel.from_dict(clip_item.model.to_dict())
        new_audio_model.uid = str(uuid.uuid4())
        new_audio_model.media_type = 'audio'
        new_audio_model.track = clip_item.track + 1
        new_audio_model.width = 0
        new_audio_model.height = 0
        clip_item.model.muted = True
        self.add_clip(new_audio_model)
        clip_item.update()
        self.data_changed.emit()

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, ClipItem):
            menu = QMenu(self)
            if item.model.media_type == 'video':
                act_split = menu.addAction("Split Audio & Video into Separate Tracks")
                act_split.triggered.connect(lambda: self.split_audio_video(item))
                menu.addSeparator()
            act_del = menu.addAction("Delete")
            act_del.triggered.connect(lambda: self.remove_selected_clips())
            menu.exec_(event.globalPos())

    def mousePressEvent(self, event):
        try:
            if self.mode == Mode.RAZOR:
                if event.button() == Qt.LeftButton:
                    item = self.itemAt(event.pos())
                    if isinstance(item, ClipItem):
                        pt = self.mapToScene(event.pos())
                        snapped_x = self.get_snapped_x(pt.x(), track_idx=item.track)
                        split_time = snapped_x / self.scale_factor
                        self.clip_split_requested.emit(item, split_time)
                return
            if event.button() == Qt.LeftButton:
                px_scene = self.playhead_pos * self.scale_factor
                px_viewport = self.mapFromScene(QPointF(px_scene, 0)).x()
                handle_rect = QRectF(px_viewport - 7, 0, 14, 15)
                if handle_rect.contains(event.pos()) or event.pos().y() < self.ruler_height:
                    self.is_dragging_playhead = True
                    self.interaction_started.emit()
                    pt = self.mapToScene(event.pos())
                    self.user_set_playhead(pt.x())
                else:
                    super().mousePressEvent(event)
            else:
                super().mousePressEvent(event)
        except Exception as e:
            self.logger.error(f"Error in mousePressEvent: {e}", exc_info=True)
            self.is_dragging_playhead = False
            
    def mouseMoveEvent(self, event):
        try:
            if event.buttons() & Qt.LeftButton and self.is_dragging_playhead:
                pt = self.mapToScene(event.pos())
                self.user_set_playhead(pt.x())
            else:
                super().mouseMoveEvent(event)
        except Exception as e:
            self.logger.error(f"Error in mouseMoveEvent: {e}", exc_info=True)
            self.is_dragging_playhead = False

    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.LeftButton and self.is_dragging_playhead:
                self.is_dragging_playhead = False
                self.interaction_ended.emit()
            super().mouseReleaseEvent(event)
            if self.scene.selectedItems():
                self.data_changed.emit()
        finally:
            self.is_dragging_playhead = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        self.logger.info(f"Drop event detected. MIME types: {event.mimeData().formats()}")
        if event.mimeData().hasUrls():
            pt = self.mapToScene(event.pos())
            track_idx = int(pt.y() // self.track_height)
            if track_idx >= self.num_tracks: track_idx = self.num_tracks - 1
            track_is_empty = True
            for item in self.scene.items():
                if isinstance(item, ClipItem) and item.track == track_idx:
                    track_is_empty = False
                    break
            time_pos = 0.0
            if not track_is_empty:
                snapped_x = self.get_snapped_x(pt.x())
                time_pos = max(0, snapped_x / self.scale_factor)
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    self.logger.info(f"Timeline Drop: {os.path.basename(path)} at Track {track_idx}, Time {time_pos:.2f}s")
                    self.file_dropped.emit(path, track_idx, time_pos)
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dropEvent(event)

    def get_snapped_x(self, x_pos, track_idx=None, ignore_item=None, threshold=20):
        if not self.snapping_enabled:
            if self.snap_line:
                self.scene.removeItem(self.snap_line)
                self.snap_line = None
            return x_pos
        snaps = [0, self.playhead_pos * self.scale_factor]
        for item in self.scene.items():
            if isinstance(item, ClipItem) and item != ignore_item:
                is_same_track = (track_idx is not None and item.track == track_idx)
                eff_threshold = threshold * 1.5 if is_same_track else threshold
                sx = item.x()
                ex = item.x() + item.rect().width()
                if abs(x_pos - sx) < eff_threshold: snaps.append(sx)
                if abs(x_pos - ex) < eff_threshold: snaps.append(ex)
        closest_snap = None
        min_dist = float('inf')
        for s in snaps:
            dist = abs(x_pos - s)
            if dist < min_dist:
                min_dist = dist
                closest_snap = s
        if min_dist > threshold:
            closest_snap = None
        if self.snap_line:
            self.scene.removeItem(self.snap_line)
            self.snap_line = None
        if closest_snap is not None:
            pen = QPen(Qt.cyan, 1)
            self.snap_line = self.scene.addLine(closest_snap, 0, closest_snap, self.scene.height(), pen)
            self.snap_line.setZValue(100)
            return closest_snap
        else:
            return x_pos

    def fit_to_view(self):
        min_start = float('inf')
        max_end = float('-inf')
        found = False
        for item in self.scene.items():
            if isinstance(item, ClipItem):
                found = True
                min_start = min(min_start, item.start)
                max_end = max(max_end, item.start + item.duration)
        if not found: return
        total_dur = max_end - min_start
        if total_dur <= 0: return
        vp_w = self.viewport().width() - 100
        if vp_w <= 0: return
        new_scale = vp_w / total_dur
        self.scale_factor = new_scale
        for item in self.scene.items():
            if isinstance(item, ClipItem):
                item.scale = self.scale_factor
                item.setPos(item.model.start * self.scale_factor, item.y())
                item.setRect(0, 0, item.model.duration * self.scale_factor, 30)
        self.horizontalScrollBar().setValue(int(min_start * self.scale_factor))
        self.scene.update()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        ruler_rect = QRectF(rect.left(), 0, rect.width(), self.ruler_height)
        painter.fillRect(ruler_rect, QColor(25, 25, 25))
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawLine(int(rect.left()), self.ruler_height, int(rect.right()), self.ruler_height)
        start_x = rect.left()
        end_x = rect.right()
        start_scene_x = self.mapToScene(QPoint(int(start_x), 0)).x()
        end_scene_x = self.mapToScene(QPoint(int(end_x), 0)).x()
        pixels_per_second = self.scale_factor
        units = [1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
        major_step_sec = units[0]
        for unit in units:
            if pixels_per_second * unit > 80:
                major_step_sec = unit
                break
        minor_step_sec = major_step_sec / 5.0
        start_sec_raw = start_scene_x / self.scale_factor
        end_sec_raw = end_scene_x / self.scale_factor
        start_unit = int(start_sec_raw / minor_step_sec) * minor_step_sec
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        sec = start_unit
        while sec < end_sec_raw:
            is_major_tick = (sec % major_step_sec) < 0.001
            scene_x = sec * self.scale_factor
            vp_x = self.mapFromScene(QPointF(scene_x, 0)).x()
            if vp_x >= start_x and vp_x <= end_x:
                if is_major_tick:
                    tick_h = 15
                    painter.setPen(QColor(220, 220, 220))
                else:
                    tick_h = 8
                    painter.setPen(QColor(150, 150, 150))
                painter.drawLine(int(vp_x), self.ruler_height - tick_h, int(vp_x), self.ruler_height)
                if is_major_tick:
                    mins = int(sec // 60)
                    secs = int(sec % 60)
                    ts = f"{mins:02}:{secs:02}"
                    painter.drawText(int(vp_x) + 4, 12, ts)
            sec += minor_step_sec
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

    def user_set_playhead(self, x):
        sec = max(0, x / self.scale_factor)
        self.playhead_pos = sec
        self.scene.update()
        self.time_updated.emit(sec)

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
        try:
            if not self.scene:
                return
            sel = self.scene.selectedItems()
            if sel and isinstance(sel[0], ClipItem):
                self.clip_selected.emit(sel[0])
            else:
                self.clip_selected.emit(None)
        except RuntimeError:
            pass

    def get_state(self):
        st = []
        if not self.scene:
            return st
        for item in self.scene.items():
            if isinstance(item, ClipItem):
                item.model.start = item.start
                item.model.duration = item.duration
                item.model.track = item.track
                st.append(item.model.to_dict())
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

    def add_clip(self, clip_data):
        if isinstance(clip_data, dict):
            model = ClipModel.from_dict(clip_data)
        elif isinstance(clip_data, ClipModel):
            model = clip_data
        else:
            raise TypeError("clip_data must be a dict or ClipModel")
        item = ClipItem(model, self.scale_factor)
        self.scene.addItem(item)
        self.fit_to_view()
        return item

    def remove_clip(self, clip_uid):
        for item in self.scene.items():
            if isinstance(item, ClipItem) and item.model.uid == clip_uid:
                self.scene.removeItem(item)
                return

    def move_clip(self, clip_uid, pos):
        for item in self.scene.items():
            if isinstance(item, ClipItem) and item.model.uid == clip_uid:
                item.setPos(pos)
                item.model.start = pos.x() / self.scale_factor
                item.model.track = int(pos.y() / self.track_height)
                return

    def set_clip_param(self, clip_uid, param, value):
        for item in self.scene.items():
            if isinstance(item, ClipItem) and item.model.uid == clip_uid:
                setattr(item.model, param, value)
                item.update()
                return

    def update_clip_proxy_path(self, source_path, proxy_path):
        for item in self.scene.items():
            if isinstance(item, ClipItem) and item.model.path == source_path:
                item.model.proxy_path = proxy_path
                return

    def get_selected_item(self):
        sel = self.scene.selectedItems()
        return sel[0] if sel else None

    def get_selected_items(self):
        return self.scene.selectedItems()

    def remove_selected_clips(self):
        for item in self.scene.selectedItems():
            self.scene.removeItem(item)
        self.compact_lanes()

    def compact_lanes(self):
        """Removes empty lanes between populated ones."""
        all_items = [item for item in self.scene.items() if isinstance(item, ClipItem)]
        if not all_items:
            return
        occupied_tracks = sorted(list(set(item.track for item in all_items)))
        if not occupied_tracks:
            return
        track_map = {}
        is_compact = True
        for i, track_idx in enumerate(occupied_tracks):
            if i != track_idx:
                is_compact = False
            track_map[track_idx] = i
        if is_compact:
            self.logger.info("Lanes are already compact.")
            return
        self.logger.info(f"Compacting lanes. Mapping: {track_map}")
        for item in all_items:
            new_track = track_map.get(item.track)
            if new_track is not None and new_track != item.track:
                item.track = new_track
                item.model.track = new_track
                item.setY(new_track * self.track_height + 35)
        self.data_changed.emit()
        self.scene.update()

    def reorder_tracks(self, source_idx, target_idx):
        if source_idx == target_idx:
            return
        self.scene.blockSignals(True)
        try:
            all_items = [it for it in self.scene.items() if isinstance(it, ClipItem)]
            items_on_source = [it for it in all_items if it.track == source_idx]
            if source_idx < target_idx:
                for it in all_items:
                    if source_idx < it.track <= target_idx:
                        it.track -= 1
                        it.model.track -= 1
                        it.setY(it.track * self.track_height + 35)
            else:
                for it in all_items:
                    if target_idx <= it.track < source_idx:
                        it.track += 1
                        it.model.track += 1
                        it.setY(it.track * self.track_height + 35)
            for it in items_on_source:
                it.track = target_idx
                it.model.track = target_idx
                it.setY(target_idx * self.track_height + 35)
        finally:
            self.scene.blockSignals(False)
        self.data_changed.emit()
        self.scene.update()
