import os
import logging
from enum import Enum
from PyQt5.QtWidgets import QGraphicsView, QMenu
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter
from timeline_scene import TimelineScene
from clip_item import ClipItem
from model import ClipModel
from timeline_grid import TimelineGridPainter
from timeline_ops import TimelineOperations

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

    def __init__(self, parent=None, main_window=None, track_headers=None):
        super().__init__(parent)
        self.mw = main_window
        self.track_headers = track_headers
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.mode = Mode.POINTER
        self.num_tracks = 6
        self.track_height = 40
        self.scale_factor = 50
        self.playhead_pos = 0.0
        self.ruler_height = 30
        self.snapping_enabled = True
        self.snap_line = None
        self.is_dragging_playhead = False
        self.is_dragging_clip = False
        self.scene = TimelineScene(self.num_tracks, self.track_height)
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.scene.selectionChanged.connect(self.on_selection_change)
        self.painter_helper = TimelineGridPainter(self.ruler_height)
        self.ops = TimelineOperations(self)

    def get_snapped_x(self, x, **kwargs):
        return self.ops.get_snapped_x(x, **kwargs)

    def compact_lanes(self):
        self.ops.compact_lanes()

    def reorder_tracks(self, s, t):
        self.ops.reorder_tracks(s, t)

    def move_clip(self, uid, pos):
        self.ops.move_clip(uid, pos)

    def set_clip_param(self, uid, p, v):
        self.ops.set_clip_param(uid, p, v)

    def update_clip_proxy_path(self, s, p):
        self.ops.update_clip_proxy_path(s, p)

    def drawForeground(self, painter, rect):
        vp_info = {'font': self.font()}
        self.painter_helper.draw_foreground(painter, rect, self.scale_factor, vp_info, self.playhead_pos)
        if self.mode == Mode.RAZOR and hasattr(self, 'razor_mouse_x'):
            self.painter_helper.draw_razor_indicator(painter, rect, self.razor_mouse_x)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            delta = -3.0 if event.modifiers() & Qt.ControlModifier else -1.0
            self.seek_request.emit(delta)
            event.accept()
        elif event.key() == Qt.Key_Right:
            delta = 3.0 if event.modifiers() & Qt.ControlModifier else 1.0
            self.seek_request.emit(delta)
            event.accept()
        elif event.key() == Qt.Key_Delete:
            if self.mw:
                self.mw.clip_ctrl.delete_current()
            event.accept()
        elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_K:
            item = self.get_selected_item()
            if item: self.clip_split_requested.emit(item, self.playhead_pos)
            event.accept()
        elif event.key() == Qt.Key_BracketLeft:
            item = self.get_selected_item()
            if item and self.playhead_pos > item.model.start:
                self.mw.save_state_for_undo()
                diff = self.playhead_pos - item.model.start
                item.model.duration = max(0.1, item.model.duration - diff)
                item.model.source_in += diff
                item.model.start = self.playhead_pos
                if item.model.linked_uid:
                    for partner in self.scene.items():
                        if isinstance(partner, ClipItem) and partner.uid == item.model.linked_uid:
                            partner.model.duration = item.model.duration
                            partner.model.source_in = item.model.source_in
                            partner.model.start = item.model.start
                self.update_clip_positions()
                self.data_changed.emit()
            event.accept()
        elif event.key() == Qt.Key_BracketRight:
            item = self.get_selected_item()
            if item and self.playhead_pos > item.model.start:
                self.mw.save_state_for_undo()
                new_dur = self.playhead_pos - item.model.start
                item.model.duration = max(0.1, new_dur)
                if item.model.linked_uid:
                    for partner in self.scene.items():
                        if isinstance(partner, ClipItem) and partner.uid == item.model.linked_uid:
                            partner.model.duration = item.model.duration
                self.update_clip_positions()
                self.data_changed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, max(3600*50, self.width()), self.num_tracks * self.track_height)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: self.zoom_in()
            else: self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self.mode == Mode.RAZOR and event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if isinstance(item, ClipItem):
                pt = self.mapToScene(event.pos())
                snapped = self.get_snapped_x(pt.x(), track_idx=item.track)
                self.clip_split_requested.emit(item, snapped / self.scale_factor)
            return
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if isinstance(item, ClipItem):
                self.is_dragging_clip = True
                self.drag_start_pos = event.pos()
                self.drag_start_item_pos = item.pos()
                self.interaction_started.emit()
                super().mousePressEvent(event)
                return
            px_scene = self.playhead_pos * self.scale_factor
            px_vp = self.mapFromScene(QPointF(px_scene, 0)).x()
            if abs(event.pos().x() - px_vp) < 10 or event.pos().y() < self.ruler_height:
                self.is_dragging_playhead = True
                self.interaction_started.emit()
                self.user_set_playhead(self.mapToScene(event.pos()).x())
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging_playhead:
            self.user_set_playhead(self.mapToScene(event.pos()).x())
        elif self.mode == Mode.RAZOR:
            self.razor_mouse_x = self.mapToScene(event.pos()).x()
            self.viewport().update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_dragging_clip:
            self.is_dragging_clip = False
            self.interaction_ended.emit()
        if self.is_dragging_playhead:
            self.is_dragging_playhead = False
            self.interaction_ended.emit()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, ClipItem):
            self.scene.clearSelection()
            item.setSelected(True)
            menu = QMenu(self)
            if item.model.media_type == 'video':
                menu.addAction("Split Audio & Video").triggered.connect(lambda: self.ops.split_audio_video(item))
                menu.addAction("Crop").triggered.connect(lambda: self.mw.toggle_crop_mode(True))
            menu.addSeparator()
            menu.addAction("Delete").triggered.connect(self.remove_selected_clips)
            menu.exec_(event.globalPos())

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            pt = self.mapToScene(event.pos())
            item = self.itemAt(event.pos())
            time_pos = 0
            if item and isinstance(item, ClipItem):
                track_idx = item.track
                time_pos = max(0, self.get_snapped_x(pt.x()) / self.scale_factor)
            else:
                track_idx = -1
                time_pos = 0
            for url in event.mimeData().urls():
                if os.path.isfile(url.toLocalFile()):
                    self.file_dropped.emit(url.toLocalFile(), track_idx, time_pos)
            event.accept()
        else:
            super().dropEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def set_mode(self, mode):
        self.mode = mode

    def toggle_snapping(self, enabled):
        self.snapping_enabled = enabled
        if not enabled and self.snap_line:
            self.scene.removeItem(self.snap_line)
            self.snap_line = None

    def zoom_in(self):
        self.scale_factor = min(self.scale_factor * 1.1, 500)
        self.update_clip_positions()

    def zoom_out(self):
        self.scale_factor = max(self.scale_factor * 0.9, 1)
        self.update_clip_positions()

    def update_clip_positions(self):
        """Goal 18: Enforces strict vertical alignment with track headers."""
        for item in self.scene.items():
            if isinstance(item, ClipItem):
                item.scale = self.scale_factor
                item.setPos(item.model.start * self.scale_factor, item.model.track * self.track_height + 30)
                item.setRect(0, 0, item.model.duration * self.scale_factor, 30)

    def user_set_playhead(self, x):
        self.set_time(max(0, x / self.scale_factor))

    def set_time(self, sec):
        self.playhead_pos = sec
        self.time_updated.emit(sec)
        self.viewport().update()
        px = sec * self.scale_factor
        val = self.horizontalScrollBar().value()
        if px > val + self.viewport().width() - 50:
            self.horizontalScrollBar().setValue(int(px - 100))
        elif px < val:
            self.horizontalScrollBar().setValue(int(px - 100))

    def set_visual_time(self, sec):
        """Updates playhead without emitting time_updated to prevent player seek loops."""
        self.playhead_pos = sec
        self.viewport().update()
        px = sec * self.scale_factor
        val = self.horizontalScrollBar().value()
        if px > val + self.viewport().width() - 50:
            self.horizontalScrollBar().setValue(int(px - 100))
        elif px < val:
            self.horizontalScrollBar().setValue(int(px - 100))

    def fit_to_view(self):
        items = [i for i in self.scene.items() if isinstance(i, ClipItem)]
        self.logger.info(f"fit_to_view called with {len(items)} items.")
        if not items: return
        start = min(i.model.start for i in items)
        end = max(i.model.start + i.model.duration for i in items)
        dur = end - start
        if dur > 0 and self.viewport().width() > 100:
            self.scale_factor = (self.viewport().width() - 100) / dur
            self.update_clip_positions()
            self.horizontalScrollBar().setValue(int(start * self.scale_factor))

    def add_clip(self, clip_data):
        model = clip_data if isinstance(clip_data, ClipModel) else ClipModel.from_dict(clip_data)
        item = ClipItem(model, self.scale_factor)
        item.setPos(model.start * self.scale_factor, model.track * self.track_height + 30)
        self.scene.addItem(item)
        return item

    def add_track_to_scene(self):
        self.set_num_tracks(self.num_tracks + 1)

    def set_num_tracks(self, num):
        self.num_tracks = num
        self.scene.setSceneRect(0, 0, self.scene.sceneRect().width(), self.num_tracks * self.track_height)

    def get_state(self):
        return [i.model.to_dict() for i in self.scene.items() if isinstance(i, ClipItem)]

    def load_state(self, state):
        self.logger.info(f"Loading timeline state with {len(state)} clips.")
        self.scene.clear()
        for c in state:
            self.add_clip(c)
        self.fit_to_view()
        self.viewport().update()

    def get_selected_item(self):
        sel = self.scene.selectedItems()
        return sel[0] if sel else None

    def get_selected_items(self):
        return self.scene.selectedItems()

    def remove_selected_clips(self):
        for item in self.scene.selectedItems():
            self.scene.removeItem(item)
        self.compact_lanes()

    def remove_clip(self, uid):
        self.ops.remove_clip(uid)

    def on_selection_change(self):
        try:
            scene = getattr(self, "scene", None)
            if scene is None: return
            sel = scene.selectedItems()
        except RuntimeError:
            return
        if sel and isinstance(sel[0], ClipItem):
            self.clip_selected.emit(sel[0])
            self.track_headers.set_selected(sel[0].track)
        else:
            self.clip_selected.emit(None)
            self.track_headers.set_selected(-1)

    def check_auto_expand(self):
        """Goal 4: Automatically create lane N only when lane N-1 is occupied."""
        items = [i for i in self.scene.items() if isinstance(i, ClipItem)]
        if not items: return
        max_occupied_track = max(i.track for i in items)
        if max_occupied_track >= self.num_tracks - 2:
            self.mw.timeline.add_track()