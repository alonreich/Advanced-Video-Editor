import os
import logging
from enum import Enum
from PyQt5.QtWidgets import QGraphicsView, QMenu, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QBrush, QColor, QLinearGradient, QPen
from timeline_scene import TimelineScene
from clip_item import ClipItem
from model import ClipModel
from timeline_grid import TimelineGridPainter
from timeline_ops import TimelineOperations
import constants

class Mode(Enum):
    POINTER = 1
    RAZOR = 2

class TimelineView(QGraphicsView):
    clip_selected = pyqtSignal(list)
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
        self.track_height = constants.TRACK_HEIGHT
        self.scale_factor = constants.DEFAULT_TIMELINE_SCALE_FACTOR
        self.playhead_pos = 0.0
        self.ruler_height = constants.RULER_HEIGHT
        self.snapping_enabled = True
        self.zoom_locked = False
        self.snap_line = None
        self.is_dragging_playhead = False
        self.is_dragging_clip = False

        from PyQt5.QtCore import QTimer
        self.scrub_throttle_timer = QTimer()
        self.scrub_throttle_timer.setSingleShot(True)
        self.scrub_throttle_timer.setInterval(16)
        self.scrub_throttle_timer.timeout.connect(self._execute_throttled_scrub)
        self._pending_scrub_x = 0
        self.active_resize_item = None
        self.scene = TimelineScene(self.num_tracks, self.track_height)
        self.setScene(self.scene)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.scene.selectionChanged.connect(self.on_selection_change)
        self.painter_helper = TimelineGridPainter(self.ruler_height)
        self.ops = TimelineOperations(self)
        self.ghost_item = None
        self.setMouseTracking(True)

    def change_clip_color(self, item):
        from PyQt5.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            item.model.color = color.name()
            item.update_cache()
            self.data_changed.emit()

    def toggle_mute(self, item):
        item.model.muted = not item.model.muted
        item.update_cache()
        self.data_changed.emit()

    def rename_clip(self, item):
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, 'Rename Clip', 'Enter new name:')
        if ok and text:
            item.model.name = text
            item.name = text
            item.update_cache()
            self.data_changed.emit()

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

    def flash_ripple_feedback(self, start_sec, track_idx):
        """Goal 5: Visual metallic green flash to confirm ripple shift."""

        from PyQt5.QtCore import QTimer
        rect = QGraphicsRectItem(start_sec * self.scale_factor, track_idx * self.track_height + constants.RULER_HEIGHT, 
                                150, self.track_height)
        grad = QLinearGradient(0, 0, 0, self.track_height)
        grad.setColorAt(0, QColor(constants.COLOR_SUCCESS))
        grad.setColorAt(1, QColor(constants.COLOR_SUCCESS).darker(150))
        rect.setBrush(QBrush(grad))
        rect.setPen(QPen(QColor(constants.COLOR_SUCCESS).lighter(120), 2))
        rect.setZValue(100)
        self.scene.addItem(rect)
        QTimer.singleShot(400, lambda: self.scene.removeItem(rect) if rect.scene() else None)

    def check_for_gaps(self, track_idx, deleted_start):
        """Goal 5: Detects if the deletion created a gap and prompts for ripple shift."""
        clips = sorted([i for i in self.scene.items() if isinstance(i, ClipItem) 
                        and i.track == track_idx], key=lambda x: x.model.start)
        found_gap = False
        gap_start, gap_end = 0.0, 0.0
        FRAME_JITTER_THRESHOLD = 0.016 
        for i in range(len(clips)):
            if clips[i].model.start > deleted_start + 0.001:
                prev_end = clips[i-1].model.start + clips[i-1].model.duration if i > 0 else 0.0
                gap_size = clips[i].model.start - prev_end
                if gap_size > 0.001:
                    gap_start = prev_end
                    gap_end = clips[i].model.start
                    if gap_size <= FRAME_JITTER_THRESHOLD:
                        shift = gap_size
                        for item in self.scene.items():
                            if isinstance(item, ClipItem):
                                if item.model.start >= gap_end - 0.001:
                                    item.model.start -= shift
                        self.update_clip_positions()
                        self.data_changed.emit()
                        return True
                    else:
                        found_gap = True
                break
        if found_gap:
            from PyQt5.QtWidgets import QGraphicsRectItem, QApplication
            rect = QGraphicsRectItem(
                gap_start * self.scale_factor,
                track_idx * self.track_height + constants.RULER_HEIGHT,
                (gap_end - gap_start) * self.scale_factor,
                self.track_height
            )
            rect.setBrush(QBrush(QColor(255, 0, 0, 100)))
            rect.setPen(Qt.NoPen)
            self.scene.addItem(rect)
            self.viewport().repaint()
            QApplication.processEvents()
            if self.prompt_close_gap():
                shift = gap_end - gap_start
                for item in self.scene.items():
                    if isinstance(item, ClipItem):
                        if item.model.start >= gap_end - 0.001:
                            item.model.start -= shift
                self.update_clip_positions()
                self.data_changed.emit()
            self.scene.removeItem(rect)
            return True
        return False

    def prompt_close_gap(self):
        """Goal 5: Prompt via Metallic Dark Green/Red dialog for ripple shift."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Gap Detected")
        msg.setText("A gap was created!\nWould you like to ripple shift clips or leave the hole?")
        msg.setStyleSheet(constants.STYLESHEET_MESSAGE_BOX)
        yes_btn = msg.addButton("Yes, Ripple Shift", QMessageBox.YesRole)
        yes_btn.setStyleSheet(constants.STYLESHEET_BUTTON_SUCCESS)
        no_btn = msg.addButton("No, Leave the Gap", QMessageBox.NoRole)
        no_btn.setStyleSheet(constants.STYLESHEET_BUTTON_ERROR)
        msg.exec_()
        return msg.clickedButton() == yes_btn
        
    def drawForeground(self, painter, rect):
        vp_info = {'font': self.font()}
        self.painter_helper.draw_foreground(painter, rect, self.scale_factor, vp_info, self.playhead_pos)
        selected = self.get_selected_item()
        if selected and hasattr(selected.model, 'scene_cuts'):
            scene_times = [t + selected.model.start for t in selected.model.scene_cuts]
            self.painter_helper.draw_scene_markers(painter, rect, self.scale_factor, scene_times)
        if self.mode == Mode.RAZOR and hasattr(self, 'razor_mouse_x'):
            self.painter_helper.draw_razor_indicator(painter, rect, self.razor_mouse_x)

    def keyPressEvent(self, event):
        """Goal 8: Aggressive seeking using Ctrl+Arrow keys."""
        is_aggressive = event.modifiers() & Qt.ControlModifier
        jump_delta = 3.0 if is_aggressive else 1.0
        frame_dur = 1.0 / 60.0
        if event.key() == Qt.Key_Left:
            delta = -3.0 if is_aggressive else -frame_dur
            self.seek_request.emit(delta)
            event.accept()
        elif event.key() == Qt.Key_Right:
            delta = 3.0 if is_aggressive else frame_dur
            self.seek_request.emit(delta)
            event.accept()
        elif event.key() == Qt.Key_P:
            if self.mw and hasattr(self.mw, 'recorder') and self.mw.recorder.is_recording:
                self.mw.recorder.toggle_pause()
                status = "PAUSED" if self.mw.recorder.is_paused else "RESUMED"
                self.mw.statusBar().showMessage(f"🔴 VOICE RECORDING: {status}")
                self.mw.preview.overlay.is_paused = self.mw.recorder.is_paused
                self.mw.preview.overlay.update()
            event.accept()
        elif event.key() == Qt.Key_Delete:
            if self.mw:
                if event.modifiers() & Qt.ShiftModifier:
                    self.mw.clip_ctrl.ripple_delete_current()
                else:
                    self.mw.clip_ctrl.delete_current()
            event.accept()
        elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_K:
            pass 
        elif event.key() in [Qt.Key_BracketLeft, Qt.Key_BracketRight]:
            item = self.get_selected_item()
            if not item:
                return
            self.mw.save_state_for_undo()
            curr_start = item.model.start
            curr_end = curr_start + item.model.duration
            playhead = self.playhead_pos
            if event.key() == Qt.Key_BracketLeft:
                if curr_start < playhead < curr_end:
                    diff = playhead - curr_start
                    item.model.source_in += diff
                    item.model.start = playhead
                    item.model.duration = max(0.1, item.model.duration - diff)
            elif event.key() == Qt.Key_BracketRight:
                if curr_start < playhead < curr_end:
                    diff = curr_end - playhead
                    item.model.duration = max(0.1, item.model.duration - diff)
            item.update_cache()
            self.update_clip_positions()
            self.data_changed.emit()
            event.accept()
        elif event.key() == Qt.Key_C:
            self.mode = Mode.RAZOR if self.mode == Mode.POINTER else Mode.POINTER
            self.logger.info(f"[MODE] Switched to {self.mode.name}")
            if hasattr(self, 'razor_mouse_x'):
                delattr(self, 'razor_mouse_x')
            if self.mw and hasattr(self.mw, 'inspector'):
                self.mw.toggle_crop_mode(self.mode == Mode.RAZOR)
            self.viewport().update()
            event.accept()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Goal 18: Ensure scene is always large enough for the current content and zoom."""
        super().resizeEvent(event)
        content_w = self.get_content_end() * self.scale_factor
        self.scene.setSceneRect(0, 0, max(content_w + 10000, self.width()), self.num_tracks * self.track_height)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: 
                self.zoom_in()
            else: 
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self.mw: self.mw.playback.player.pause()
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        item = self.itemAt(event.pos())
        if isinstance(item, ClipItem):
            if not item.isSelected():
                self.is_dragging_clip = True
                self.drag_start_pos = event.pos()
                super().mousePressEvent(event)
                self.drag_start_item_positions = {i: i.pos() for i in self.scene.selectedItems()}
                self.interaction_started.emit()
                return
            item.update_handle_rects()
            item_pos = item.mapFromScene(self.mapToScene(event.pos()))
            is_bottom_half = item_pos.y() > (item.rect().height() / 2)
            if item.left_handle_rect.contains(item_pos):
                self.active_resize_item = item
                self.resize_drag_mode = 'fade_in' if is_bottom_half else 'left'
                self.drag_start_pos = self.mapToScene(event.pos())
                self.drag_start_geometry = (item.pos().x(), item.rect().width(), item.model.fade_in)
                self.interaction_started.emit()
                return
            elif item.right_handle_rect.contains(item_pos):
                self.active_resize_item = item
                self.resize_drag_mode = 'fade_out' if is_bottom_half else 'right'
                self.drag_start_pos = self.mapToScene(event.pos())
                self.drag_start_geometry = (item.pos().x(), item.rect().width(), item.model.fade_out)
                self.interaction_started.emit()
                return
            elif item.model.media_type != 'audio' and item.right_handle_rect.contains(item_pos):
                self.active_resize_item = item
                self.resize_drag_mode = 'right'
                self.drag_start_pos = self.mapToScene(event.pos())
                self.drag_start_geometry = (item.pos().x(), item.rect().width())
                self.interaction_started.emit()
                return
            else:
                self.is_dragging_clip = True
                self.drag_start_pos = event.pos()
                super().mousePressEvent(event)
                self.drag_start_item_positions = {i: i.pos() for i in self.scene.selectedItems()}
                self.interaction_started.emit()
                return
        if self.mode == Mode.RAZOR:
            if isinstance(item, ClipItem):
                pt = self.mapToScene(event.pos())
                snapped_x = self.get_snapped_x(pt.x(), track_idx=item.track, threshold=20)
                self.clip_split_requested.emit(item, snapped_x / self.scale_factor)
                if self.snap_line: self.snap_line.hide()
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
        frame_dur = 1.0 / 60.0 
        if self.is_dragging_clip or self.active_resize_item:
            if self.mw and hasattr(self.mw, 'playback'):
                self.mw.playback.player.pause()
        if self.active_resize_item:
            item = self.active_resize_item
            current_x_scene = self.mapToScene(event.pos()).x()
            delta_x = current_x_scene - self.drag_start_pos.x()
            start_x, start_w, start_fade = self.drag_start_geometry or (0,0,0)
            if self.resize_drag_mode == 'fade_in':
                delta_sec = (self.mapToScene(event.pos()).x() - item.pos().x()) / self.scale_factor
                snapped_fade = round(delta_sec / frame_dur) * frame_dur
                item.model.fade_in = max(0, min(snapped_fade, item.model.duration / 2))
                item.update_cache()
            elif self.resize_drag_mode == 'fade_out':
                edge_x = item.pos().x() + item.rect().width()
                delta_sec = (edge_x - self.mapToScene(event.pos()).x()) / self.scale_factor
                snapped_fade = round(delta_sec / frame_dur) * frame_dur
                item.model.fade_out = max(0, min(snapped_fade, item.model.duration / 2))
                item.update_cache()
            elif self.resize_drag_mode == 'right':
                new_w = start_w + delta_x
                next_clip_x = float('inf')
                for other in self.scene.items():
                    if isinstance(other, ClipItem) and other != item and other.track == item.track and other.pos().x() > item.pos().x():
                        next_clip_x = min(next_clip_x, other.pos().x())
                new_w = min(new_w, next_clip_x - item.pos().x())
                new_w = max(10, new_w)
                new_duration = round((new_w / self.scale_factor) / frame_dur) * frame_dur
                source_playable_duration = (item.model.source_duration - item.model.source_in) * item.model.speed
                if new_duration > source_playable_duration:
                    item.model.end_freeze = new_duration - source_playable_duration
                else:
                    item.model.end_freeze = 0
                item.model.duration = new_duration
            elif self.resize_drag_mode == 'left':
                new_x = start_x + delta_x
                new_w = start_w - delta_x
                prev_clip_end_x = float('-inf')
                for other in self.scene.items():
                    if isinstance(other, ClipItem) and other != item and other.track == item.track and other.pos().x() < item.pos().x():
                        prev_clip_end_x = max(prev_clip_end_x, other.pos().x() + other.rect().width())
                new_x = max(new_x, prev_clip_end_x)
                new_w = (start_x + start_w) - new_x
                new_w = max(10, new_w)
                new_x = (start_x + start_w) - new_w
                new_start = new_x / self.scale_factor
                new_duration = new_w / self.scale_factor
                delta_t = item.model.start - new_start
                if (item.model.source_in + delta_t) < 0:
                    item.model.start_freeze = -(item.model.source_in + delta_t)
                    item.model.source_in = 0
                else:
                    item.model.start_freeze = 0
                    item.model.source_in += delta_t
                item.model.start = new_start
                item.model.duration = new_duration
            if item.model.linked_uid:
                for other in self.scene.items():
                    if isinstance(other, ClipItem) and other.uid == item.model.linked_uid:
                        other.model.start = item.model.start
                        other.model.duration = item.model.duration
                        other.model.source_in = item.model.source_in
                        other.model.start_freeze = item.model.start_freeze
                        other.model.end_freeze = item.model.end_freeze
                        break
            self.update_clip_positions()
            self.data_changed.emit()
            return
        selection = []
        if self.is_dragging_clip:
            selection = list(self.drag_start_item_positions.keys())
        if self.is_dragging_clip and selection:
            if self.mw: self.mw.playback.player.pause()
            main_item = selection[0]
            main_item_start_pos = self.drag_start_item_positions[main_item]
            raw_delta_x = self.mapToScene(event.pos()).x() - self.drag_start_pos.x()
            raw_y = self.mapToScene(event.pos()).y()
            new_track = max(0, int((raw_y - self.ruler_height) / self.track_height))
            raw_x = main_item_start_pos.x() + raw_delta_x
            if self.snapping_enabled:
                visible_items = self.items(self.viewport().rect())
                snapped_x = self.ops.get_snapped_x(raw_x, track_idx=new_track, ignore_items=selection, 
                                                    threshold=20, items_to_check=visible_items)
                raw_delta_x = snapped_x - main_item_start_pos.x()
            can_move = True
            for item in selection:
                start_pos = self.drag_start_item_positions[item]
                new_x = start_pos.x() + raw_delta_x
                for other in self.scene.items():
                    if isinstance(other, ClipItem) and other not in selection and other.track == new_track:
                        if (new_x < other.x() + other.rect().width()) and (new_x + item.rect().width() > other.x()):
                            if item.track != new_track:
                                old_track = item.track
                                other.track = old_track
                                other.model.track = old_track
                                other.setY(old_track * self.track_height + constants.RULER_HEIGHT)
                                other.update_cache()
                            else:
                                can_move = False
                                break
            if can_move:
                for item in selection:
                    start_pos = self.drag_start_item_positions[item]
                    new_x = start_pos.x() + raw_delta_x
                    new_x = max(0, new_x)
                    snapped_start = round((new_x / self.scale_factor) / frame_dur) * frame_dur
                    item.setPos(snapped_start * self.scale_factor, new_track * self.track_height + constants.RULER_HEIGHT)
                    item.track = new_track
                    item.model.track = new_track
                    item.model.start = snapped_start
                    item.update_cache()
                    item.update()
            if not self.ghost_item:
                from PyQt5.QtWidgets import QGraphicsRectItem
                self.ghost_item = QGraphicsRectItem()
                self.ghost_item.setBrush(QColor(255, 255, 255, 80))
                self.ghost_item.setPen(QPen(Qt.cyan, 1, Qt.DashLine))
                self.ghost_item.setZValue(99)
                self.scene.addItem(self.ghost_item)
            main_item = selection[0]
            self.ghost_item.setRect(0, 0, main_item.rect().width(), main_item.rect().height())
            self.ghost_item.setPos(main_item.pos())
            self.ghost_item.show()
            if not self.scrub_throttle_timer.isActive():
                self.scrub_throttle_timer.start()
            return
        if self.is_dragging_playhead:
            self._pending_scrub_x = self.mapToScene(event.pos()).x()
            if not self.scrub_throttle_timer.isActive():
                self.scrub_throttle_timer.start()
        elif self.mode == Mode.RAZOR:
            scene_pos = self.mapToScene(event.pos())
            self.razor_mouse_x = self.ops.get_snapped_x(scene_pos.x(), items_to_check=self.items(self.viewport().rect())) if self.snapping_enabled else scene_pos.x()
            self.viewport().update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.active_resize_item:
            self.update_clip_positions()
            self.active_resize_item = None
            self.interaction_ended.emit()
            self.data_changed.emit()
            return
        if self.is_dragging_clip:
            self.is_dragging_clip = False
            if self.snap_line:
                self.scene.removeItem(self.snap_line)
            if self.ghost_item:
                self.scene.removeItem(self.ghost_item)
                self.ghost_item = None
            self.snap_line = None
            for item in self.get_selected_items():
                item.is_colliding = False
                item.setToolTip("")
                item.model.start = item.x() / self.scale_factor
                item.model.track = int((item.y() - constants.RULER_HEIGHT) / self.track_height)
                item.update_cache()
                item.update()
            self.mw.save_state_for_undo()
            self.mw.timeline.update_tracks()
            self.compact_lanes()
        if self.is_dragging_playhead:
            self.is_dragging_playhead = False
            if self.mw:
                self.mw.playback.mark_dirty(serious=True)
            if self.snap_line:
                self.scene.removeItem(self.snap_line)
                self.snap_line = None
            self.interaction_ended.emit()

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, ClipItem):
            self.scene.clearSelection()
            item.setSelected(True)
            menu = QMenu(self)
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
            snapped_x = self.ops.get_snapped_x(pt.x(), threshold=20) 
            time_pos = max(0, snapped_x / self.scale_factor)
            if self.snap_line: self.snap_line.hide()
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
                item.setPos(item.model.start * self.scale_factor, item.model.track * self.track_height + constants.RULER_HEIGHT)
                total_duration = item.model.duration + item.model.start_freeze + item.model.end_freeze
                item.setRect(0, 0, total_duration * self.scale_factor, 30)

    def user_set_playhead(self, x):
        """Goal 8: Frame-accurate scrubbing with absolute pixel locking."""
        frame_dur = 1.0 / 60.0
        sec = round((x / self.scale_factor) / frame_dur) * frame_dur
        sec = max(0, sec)
        if x >= self.scene.width() - 50:
            self.scene.setSceneRect(0, 0, x + 10000, self.scene.height())
        self.playhead_pos = sec
        self.viewport().update()
        px, val, vw = sec * self.scale_factor, self.horizontalScrollBar().value(), self.viewport().width()
        if px > val + vw - 50:
            self.horizontalScrollBar().setValue(int(px - vw + 100))
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

    def set_visual_time(self, sec, follow=False):
        """Goal 8: Updates playhead with intelligent auto-scroll for recording/playback."""
        self.playhead_pos = sec
        self.viewport().update()
        px = sec * self.scale_factor
        scrollbar = self.horizontalScrollBar()
        val = scrollbar.value()
        viewport_w = self.viewport().width()
        if follow:
            if px > val + (viewport_w * 0.7) or px < val + (viewport_w * 0.1):
                target_scroll = int(px - (viewport_w / 3))
                scrollbar.setValue(max(0, target_scroll))
        else:
            if px > val + viewport_w - 50:
                scrollbar.setValue(int(px - 100))
            elif px < val:
                scrollbar.setValue(int(px - 100))

    def fit_to_view(self, force=False):
        """Goal 18: Intelligent scaling that respects user zoom locks."""
        if self.zoom_locked and not force:
            return
        end_time = self.get_content_end()
        duration = max(10.0, end_time)
        if self.viewport().width() > 100:
            margin_px = 40
            available_width = self.viewport().width() - (margin_px * 2)
            self.scale_factor = available_width / duration
            self.scale_factor = max(1.0, min(self.scale_factor, 500.0))
            self.update_clip_positions()
            self.horizontalScrollBar().setValue(0)
            self.logger.info(f"[ZOOM] Auto-fit to {duration:.2f}s (Scale: {self.scale_factor:.2f})")

    def add_clip(self, clip_data):
        model = clip_data if isinstance(clip_data, ClipModel) else ClipModel.from_dict(clip_data)
        item = ClipItem(model, self.scale_factor)
        item.setPos(model.start * self.scale_factor, model.track * self.track_height + constants.RULER_HEIGHT)
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
        if sel:
            self.clip_selected.emit(sel)
            if isinstance(sel[0], ClipItem):
                self.track_headers.set_selected(sel[0].track)
        else:
            self.clip_selected.emit([])
            self.track_headers.set_selected(-1)

    def _execute_throttled_scrub(self):
        """Executes the stored seek request once the throttle interval passes."""
        self.user_set_playhead(self._pending_scrub_x)