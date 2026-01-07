from PyQt5.QtWidgets import QGraphicsRectItem, QMessageBox, QPushButton
from PyQt5.QtGui import QBrush, QColor
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
        self.num_tracks = 2
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
        self.setMouseTracking(True)

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

    def check_for_gaps(self, track_idx, deleted_start):
        """Detects if a hole was left between clips and prompts the user."""
        clips = sorted([i for i in self.scene.items() if isinstance(i, ClipItem) and i.track == track_idx], 
                       key=lambda x: x.model.start)
        gap_start, gap_end, found_gap = 0.0, 0.0, False
        for i in range(len(clips) - 1):
            end_current = clips[i].model.start + clips[i].model.duration
            start_next = clips[i+1].model.start
            if start_next > end_current + 0.001:
                gap_start, gap_end = end_current, start_next
                found_gap = True
                break
        if found_gap:
            rect = QGraphicsRectItem(gap_start * self.scale_factor, track_idx * self.track_height + 30, 
                                    (gap_end - gap_start) * self.scale_factor, self.track_height)
            rect.setBrush(QBrush(QColor(255, 0, 0, 100))) 
            rect.setPen(Qt.NoPen)
            self.scene.addItem(rect)
            if self.prompt_close_gap():
                shift = gap_end - gap_start
                for clip in clips:
                    if clip.model.start >= gap_end:
                        clip.model.start -= shift
                self.update_clip_positions()
                self.data_changed.emit()
            self.scene.removeItem(rect)

    def prompt_close_gap(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Gap Detected")
        msg.setText("A gap was created! Would you like me to close the gap by shifting clips to the left?")
        yes_btn = msg.addButton("Yes", QMessageBox.YesRole)
        yes_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2E4D2E, stop:1 #0F1A0F);
            color: #A0D0A0; border: 1px solid #050A05; font-weight: bold; padding: 10px;
        """)
        no_btn = msg.addButton("No. Leave the gap as it is", QMessageBox.NoRole)
        no_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5C1A1A, stop:1 #240909);
            color: #D0A0A0; border: 1px solid #120303; font-weight: bold; padding: 10px;
        """)
        msg.exec_()
        return msg.clickedButton() == yes_btn

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
                self.fit_to_view()
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
                self.fit_to_view()
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
        if self.is_dragging_clip:
            item = self.get_selected_item()
            if item:
                delta = self.mapToScene(event.pos()) - self.mapToScene(self.drag_start_pos)
                raw_x = self.drag_start_item_pos.x() + delta.x()
                new_x = self.get_snapped_x(raw_x, ignore_item=item) if self.snapping_enabled else raw_x
                track = max(0, min(self.num_tracks - 1, round((self.drag_start_item_pos.y() + delta.y() - self.ruler_height) / self.track_height)))
                new_y = (track * self.track_height) + self.ruler_height
                collision = any(i for i in self.scene.items() if isinstance(i, ClipItem) and i != item and i.track == track and i.x() < new_x + item.rect().width() - 1 and i.x() + i.rect().width() > new_x + 1)
                if not collision:
                    item.setPos(QPointF(new_x, new_y))
                    item.model.track, item.model.start = track, new_x / self.scale_factor
                    item.is_colliding = False
                    item.setToolTip("")
                else:
                    item.is_colliding = True
                    item.setToolTip("LANE BLOCKED: Overlap not allowed.")
                item.update_cache()
                item.update()
        elif self.is_dragging_playhead:
            self.user_set_playhead(self.mapToScene(event.pos()).x())
        elif self.mode == Mode.RAZOR:
            raw_x = self.mapToScene(event.pos()).x()
            self.razor_mouse_x = self.get_snapped_x(raw_x)
            self.viewport().update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_dragging_clip:
            self.is_dragging_clip = False
            if self.snap_line:
                self.scene.removeItem(self.snap_line)
                self.snap_line = None
            item = self.get_selected_item()
            if item:
                item.is_colliding = False
                item.setToolTip("")
                colliding_items = [i for i in self.scene.items() if isinstance(i, ClipItem) and i != item and i.track == item.track and i.collidesWithItem(item)]
                if colliding_items:
                    target = colliding_items[0]
                    if item.x() + (item.rect().width() / 2) < target.x() + (target.rect().width() / 2):
                        new_x = target.x() - item.rect().width()
                    else:
                        new_x = target.x() + target.rect().width()
                    item.setX(max(0, new_x))
                item.model.start = item.x() / self.scale_factor
                item.update_cache()
                item.update()
            self.compact_lanes()
            self.interaction_ended.emit()

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
                self.mw.statusBar().showMessage("CANNOT IMPORT: Space already occupied on this track.", 3000)
                event.ignore()
                return
            track_idx = max(0, round((pt.y() - self.ruler_height) / self.track_height))
            time_pos = max(0, self.get_snapped_x(pt.x()) / self.scale_factor)
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
        sec = max(0, x / self.scale_factor)
        self.playhead_pos = sec
        self.viewport().update()
        px = sec * self.scale_factor
        val = self.horizontalScrollBar().value()
        viewport_w = self.viewport().width()
        if px > val + viewport_w - 50:
            self.horizontalScrollBar().setValue(int(px - viewport_w + 100))
        elif px < val:
            self.horizontalScrollBar().setValue(int(px - 100))
        self.time_updated.emit(sec)

    def set_time(self, sec):
        if self.is_dragging_playhead:
            return
        self.playhead_pos = sec
        self.viewport().update()
        px = sec * self.scale_factor
        val = self.horizontalScrollBar().value()
        viewport_w = self.viewport().width()
        if px > val + viewport_w - 50:
             self.horizontalScrollBar().setValue(int(px - 50))

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

    def remove_track_from_scene(self):
        if self.num_tracks > 0:
            self.set_num_tracks(self.num_tracks - 1)

    def set_num_tracks(self, num):
        self.num_tracks = num
        self.scene.setSceneRect(0, 0, self.scene.sceneRect().width(), self.num_tracks * self.track_height)

    def get_state(self):
        return [i.model.to_dict() for i in self.scene.items() if isinstance(i, ClipItem)]

    def get_content_end(self):
        """Calculates the end time of the last clip on the timeline."""
        items = [i for i in self.scene.items() if isinstance(i, ClipItem)]
        if not items:
            return 0.0
        return max(i.model.start + i.model.duration for i in items)

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