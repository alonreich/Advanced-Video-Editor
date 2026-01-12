from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QApplication
from PyQt5.QtGui import QPainter, QColor, QPen, QRegion, QPainterPath
from PyQt5.QtCore import Qt, QRect, QPointF, QRectF, pyqtSignal, QTimer
import logging
import constants

class PopOutPlayerWindow(QWidget):

    def __init__(self, player_widget, preview_widget):
        super().__init__()
        self.player = player_widget
        self.preview_widget = preview_widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.player)
        self.setWindowTitle("Preview")

    def closeEvent(self, event):
        self.preview_widget.toggle_popout()
        event.accept()

    def moveEvent(self, event):
        self._save_geometry()
        super().moveEvent(event)

    def resizeEvent(self, event):
        self._save_geometry()
        super().resizeEvent(event)

    def _save_geometry(self):
        """Remember monitor, size, and position immediately."""
        if hasattr(self.preview_widget, 'mw') and self.preview_widget.mw:
            rect = self.geometry()
            geo_str = f"{rect.x()},{rect.y()},{rect.width()},{rect.height()}"
            self.preview_widget.mw.config.set("popout_geometry", geo_str)

class SafeOverlay(QWidget):
    param_changed = pyqtSignal(str, float)
    interaction_started = pyqtSignal()
    interaction_ended = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.selected_clip = None
        self.crop_mode = False
        self.dragging = False
        self.drag_handle = None
        self.drag_start_pos = QPointF()
        self.drag_start_rect = QRectF()
        self.drag_start_clip_pos = (0, 0)
        self.drag_start_clip_scale = (1, 1)
        self.transform_rect = QRectF()
        self.crop_rect = QRectF()
        self.handles = []
        self.handle_size = 14
        self.dash_offset = 0
        self.is_loading = False
        self.loading_angle = 0
        self.is_recording = False
        self.is_paused = False
        self.target_res = (1920, 1080)
        self.mode = "Landscape"
        self.dash_timer = QTimer(self)
        self.dash_timer.timeout.connect(self.update_dash_offset)
        self.dash_timer.start(100)
        self.is_snapped_x = False
        self.is_snapped_y = False
        self.backup_crop = {}
        self.seek_accel = 1.0
        self.show_speedo = False
        self.btn_confirm = QPushButton("✔ APPLY CROP", self)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setToolTip("Apply crop adjustments")
        self.btn_confirm.clicked.connect(self.confirm_crop)
        self.btn_confirm.setStyleSheet(constants.STYLESHEET_BUTTON_SUCCESS)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.hide()
        self.btn_cancel = QPushButton("âœ– CANCEL", self)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setToolTip("Cancel crop adjustments")
        self.btn_cancel.clicked.connect(self.cancel_crop)
        self.btn_cancel.setStyleSheet(constants.STYLESHEET_BUTTON_ERROR)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.hide()
        self.logger = logging.getLogger(__name__)

    def set_mode(self, width, height, mode_name):
        self.target_res = (width, height)
        self.mode = "Portrait" if "Portrait" in mode_name else "Landscape"
        self.update()

    def update_dash_offset(self):
        self.dash_offset = (self.dash_offset + 1) % 10
        self.update()

    def set_selected_clip(self, clip_model):
        self.selected_clip = clip_model
        self.update()

    def toggle_crop_mode(self):
        self.crop_mode = not self.crop_mode
        if self.crop_mode and self.selected_clip:
            if hasattr(self.parent(), 'apply_crop'):
                self.parent().apply_crop(None) 
            self.backup_crop = {
                'crop_x1': self.selected_clip.crop_x1,
                'crop_y1': self.selected_clip.crop_y1,
                'crop_x2': self.selected_clip.crop_x2,
                'crop_y2': self.selected_clip.crop_y2
            }
            self.btn_confirm.raise_()
            self.btn_cancel.raise_()
            self.btn_confirm.show()
            self.btn_cancel.show()
        else:
            if hasattr(self.parent(), 'apply_crop'):
                self.parent().apply_crop(self.selected_clip)
            self.btn_confirm.hide()
            self.btn_cancel.hide()
        self.update()
        if self.parent():
            self.parent().update()

    def confirm_crop(self):
        self.toggle_crop_mode()
        if self.parent() and hasattr(self.parent().parent(), 'btn_crop'):
            self.parent().parent().btn_crop.setChecked(False)

    def cancel_crop(self):
        if self.backup_crop:
            for k, v in self.backup_crop.items():
                self.param_changed.emit(k, v)
        self.toggle_crop_mode()
        
    def resizeEvent(self, event):
        w = event.size().width()
        h = event.size().height()
        self.btn_cancel.setGeometry(20, 20, 160, 45)
        self.btn_confirm.setGeometry(w - 180, 20, 160, 45)
        super().resizeEvent(event)

    def get_video_rect(self):
        w, h = self.width(), self.height()
        target_w, target_h = self.target_res
        if target_w == 0 or target_h == 0: return QRectF(self.rect())
        scale = min(w / target_w, h / target_h)
        nw, nh = target_w * scale, target_h * scale
        nx, ny = (w - nw) / 2, (h - nh) / 2
        return QRectF(nx, ny, nw, nh)

    def to_video_coords(self, widget_pos):
        v_rect = self.get_video_rect()
        norm_x = (widget_pos.x() - v_rect.left()) / v_rect.width()
        norm_y = (widget_pos.y() - v_rect.top()) / v_rect.height()
        return norm_x, norm_y

    def paintEvent(self, e):
        """Goal 10: Renders out-of-bounds media at 50% transparency for editing clarity."""
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        v_rect = self.get_video_rect()
        if self.mode == "Portrait":
            self.draw_portrait_guides(p, v_rect)
        try:
            p.save()
            p.setClipRect(v_rect)
            if self.is_recording:
                if self.is_paused:
                    p.setBrush(QColor(255, 255, 0))
                    p.setPen(Qt.NoPen)
                    p.drawRect(20, 20, 5, 15)
                    p.drawRect(30, 20, 5, 15)
                    p.setPen(QPen(Qt.white, 1))
                    p.drawText(40, 32, "PAUSED")
                else:
                    p.setBrush(QColor(255, 0, 0))
                    p.setPen(Qt.NoPen)
                    if (self.dash_offset // 2) % 2 == 0:
                        p.drawEllipse(20, 20, 15, 15)
                    p.setPen(QPen(Qt.white, 1))
                    p.drawText(40, 32, "REC")
            if not self.selected_clip:
                return
            if self.dragging and self.crop_mode:
                p.setPen(QPen(QColor(255, 255, 255, 180), 1, Qt.DashLine))
                if self.is_snapped_x:
                    p.drawLine(int(v_rect.center().x()), int(v_rect.top()), int(v_rect.center().x()), int(v_rect.bottom()))
                if self.is_snapped_y:
                    p.drawLine(int(v_rect.left()), int(v_rect.center().y()), int(v_rect.right()), int(v_rect.center().y()))
            if self.is_loading:
                try:
                    p.save()
                    p.setRenderHint(QPainter.Antialiasing)
                    p.setPen(QPen(QColor(0, 255, 255), 4, Qt.SolidLine, Qt.RoundCap))
                    center = v_rect.center()
                    spinner_rect = QRectF(center.x() - 25, center.y() - 25, 50, 50)
                    self.loading_angle = (self.loading_angle + 10) % 360
                    p.drawArc(spinner_rect, -self.loading_angle * 16, 120 * 16)
                finally:
                    p.restore()
                self.update()
            if self.crop_mode:
                self.draw_crop_controls(p, v_rect)
            else:
                self.draw_transform_controls(p, v_rect)
            if self.show_speedo and self.seek_accel > 1.1:
                self.draw_speedometer(p)
        finally:
            p.restore()

    def draw_portrait_guides(self, p, v_rect):
        """Goal 16: Dim out the 'cut-off' areas for center-cut Portrait export."""
        widget_rect = self.rect()
        p.save()
        bg_path = QPainterPath()
        bg_path.addRect(QRectF(widget_rect))
        bg_path.addRect(v_rect)
        p.setClipPath(bg_path)
        p.fillRect(widget_rect, QColor(0, 0, 0, 180))
        p.restore()
        portrait_width = v_rect.height() * (9 / 16)
        center_x = v_rect.center().x()
        left_edge = center_x - (portrait_width / 2)
        right_edge = center_x + (portrait_width / 2)
        p.save()
        p.setBrush(QColor(0, 0, 0, 140))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(v_rect.left(), v_rect.top(), left_edge - v_rect.left(), v_rect.height()))
        p.drawRect(QRectF(right_edge, v_rect.top(), v_rect.right() - right_edge, v_rect.height()))
        p.setPen(QPen(QColor(0, 255, 255, 200), 2, Qt.DashLine))
        p.drawRect(QRectF(left_edge, v_rect.top(), portrait_width, v_rect.height()))
        p.restore()

    def draw_transform_controls(self, p, v_rect):
        sx, sy = self.selected_clip.scale_x, self.selected_clip.scale_y
        px, py = self.selected_clip.pos_x, self.selected_clip.pos_y
        center_x = v_rect.left() + v_rect.width() * 0.5
        center_y = v_rect.top() + v_rect.height() * 0.5
        draw_x = center_x + (px * v_rect.width())
        draw_y = center_y - (py * v_rect.height())
        draw_w = v_rect.width() * sx
        draw_h = v_rect.height() * sy
        final_x = draw_x - (draw_w / 2)
        final_y = draw_y - (draw_h / 2)
        self.transform_rect = QRectF(final_x, final_y, draw_w, draw_h)
        p.setPen(QPen(QColor(0, 150, 255), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.transform_rect)
        self.update_handles()
        p.setBrush(QColor(0, 150, 255))
        for handle in self.handles:
            p.drawRect(handle)

    def draw_crop_controls(self, p, v_rect):
        c = self.selected_clip
        x = v_rect.left() + (c.crop_x1 * v_rect.width())
        y = v_rect.top() + (c.crop_y1 * v_rect.height())
        w = (c.crop_x2 - c.crop_x1) * v_rect.width()
        h = (c.crop_y2 - c.crop_y1) * v_rect.height()
        self.crop_rect = QRectF(x, y, w, h)
        pen = QPen(Qt.yellow, 2, Qt.CustomDashLine)
        pen.setDashPattern([5, 5])
        pen.setDashOffset(self.dash_offset)
        p.setPen(pen)
        p.drawRect(self.crop_rect)
        self.update_handles(for_crop=True)
        p.setBrush(Qt.yellow)
        p.setPen(QPen(Qt.black, 1))
        for handle in self.handles:
            p.drawRect(handle)

    def update_handles(self, for_crop=False):
        self.handles = []
        r = self.crop_rect if for_crop else self.transform_rect
        hs = self.handle_size
        self.handles.append(QRectF(r.left() - hs/2, r.top() - hs/2, hs, hs))
        self.handles.append(QRectF(r.right() - hs/2, r.top() - hs/2, hs, hs))
        self.handles.append(QRectF(r.right() - hs/2, r.bottom() - hs/2, hs, hs))
        self.handles.append(QRectF(r.left() - hs/2, r.bottom() - hs/2, hs, hs))

    def handle_arrow_keys(self, event):
        if not self.selected_clip or not self.crop_mode: return
        step = 0.005
        dx, dy = 0.0, 0.0
        if event.key() == Qt.Key_Left: dx = -step
        elif event.key() == Qt.Key_Right: dx = step
        elif event.key() == Qt.Key_Up: dy = -step
        elif event.key() == Qt.Key_Down: dy = step
        c = self.selected_clip
        w = c.crop_x2 - c.crop_x1
        h = c.crop_y2 - c.crop_y1
        nx1 = max(0.0, min(1.0 - w, c.crop_x1 + dx))
        ny1 = max(0.0, min(1.0 - h, c.crop_y1 + dy))
        self.param_changed.emit("crop_x1", nx1)
        self.param_changed.emit("crop_y1", ny1)
        self.param_changed.emit("crop_x2", nx1 + w)
        self.param_changed.emit("crop_y2", ny1 + h)
        self.update()

    def mousePressEvent(self, event):
        try:
            if not self.selected_clip: return
            self.drag_start_pos = event.pos()
            if self.crop_mode:
                for i, handle in enumerate(self.handles):
                    if handle.contains(event.pos()):
                        self.dragging = True
                        self.drag_handle = i
                        self.drag_start_rect = QRectF(self.crop_rect)
                        self.interaction_started.emit()
                        return
                if self.crop_rect.contains(event.pos()):
                    self.dragging = True
                    self.drag_handle = "crop_pan"
                    self.drag_start_rect = QRectF(self.crop_rect)
                    self.interaction_started.emit()
                    return
                self.dragging = True
                self.drag_handle = "crop_draw"
                self.interaction_started.emit()
                return
            for i, handle in enumerate(self.handles):
                if handle.contains(event.pos()):
                    self.dragging = True
                    self.drag_handle = i
                    self.drag_start_rect = QRectF(self.transform_rect)
                    self.drag_start_clip_scale = (self.selected_clip.scale_x, self.selected_clip.scale_y)
                    self.drag_start_clip_pos = (self.selected_clip.pos_x, self.selected_clip.pos_y)
                    self.interaction_started.emit()
                    return
            if self.transform_rect.contains(event.pos()):
                self.dragging = True
                self.drag_handle = "move"
                self.drag_start_clip_pos = (self.selected_clip.pos_x, self.selected_clip.pos_y)
                self.interaction_started.emit()
        except Exception as e:
            self.dragging = False
            self.drag_handle = None
            self.logger.error(f"[OVERLAY] Press Error: {e}")

    def mouseMoveEvent(self, event):
        try:
            if not self.dragging or not self.selected_clip:
                return
            v_rect = self.get_video_rect()
            if v_rect.width() == 0 or v_rect.height() == 0:
                return
            delta = event.pos() - self.drag_start_pos
            dx_norm = delta.x() / v_rect.width()
            dy_norm = delta.y() / v_rect.height()
            if self.crop_mode:
                if self.drag_handle == "crop_pan":
                    start_x, start_y = self.to_video_coords(self.drag_start_pos)
                    curr_x, curr_y = self.to_video_coords(event.pos())
                    dx = curr_x - start_x
                    dy = curr_y - start_y
                    old_c = self.selected_clip
                    w = old_c.crop_x2 - old_c.crop_x1
                    h = old_c.crop_y2 - old_c.crop_y1
                    new_x1 = max(0.0, min(1.0 - w, old_c.crop_x1 + dx))
                    new_y1 = max(0.0, min(1.0 - h, old_c.crop_y1 + dy))
                    self.param_changed.emit("crop_x1", new_x1)
                    self.param_changed.emit("crop_y1", new_y1)
                    self.param_changed.emit("crop_x2", new_x1 + w)
                    self.param_changed.emit("crop_y2", new_y1 + h)
                    self.drag_start_pos = event.pos()
                elif self.drag_handle == "crop_draw":
                    start_x, start_y = self.to_video_coords(self.drag_start_pos)
                    curr_x, curr_y = self.to_video_coords(event.pos())
                    x1, y1 = max(0.0, min(1.0, min(start_x, curr_x))), max(0.0, min(1.0, min(start_y, curr_y)))
                    x2, y2 = max(0.0, min(1.0, max(start_x, curr_x))), max(0.0, min(1.0, max(start_y, curr_y)))
                    if (x2 - x1) > 0.05 and (y2 - y1) > 0.05:
                        self.param_changed.emit("crop_x1", x1)
                        self.param_changed.emit("crop_y1", y1)
                        self.param_changed.emit("crop_x2", x2)
                        self.param_changed.emit("crop_y2", y2)
                elif isinstance(self.drag_handle, int):
                    aspect = self.target_res[0] / self.target_res[1]
                    min_h = 20
                    if self.drag_handle in [0, 1]:
                        avail_h = self.drag_start_rect.bottom() - v_rect.top()
                        avail_w = (v_rect.right() - self.drag_start_rect.left()) if self.drag_handle == 1 else (self.drag_start_rect.right() - v_rect.left())
                    else:
                        avail_h = v_rect.bottom() - self.drag_start_rect.top()
                        avail_w = (v_rect.right() - self.drag_start_rect.left()) if self.drag_handle == 2 else (self.drag_start_rect.right() - v_rect.left())
                    max_h = min(avail_h, avail_w / aspect)
                    raw_h = (self.drag_start_rect.height() - dy_norm * v_rect.height()) if self.drag_handle in [0, 1] else (self.drag_start_rect.height() + dy_norm * v_rect.height())
                    new_h = max(min_h, min(raw_h, max_h))
                    new_w = new_h * aspect
                if self.drag_handle == 0: 
                    new_rect = QRectF(self.drag_start_rect.right() - new_w, self.drag_start_rect.bottom() - new_h, new_w, new_h)
                elif self.drag_handle == 1: 
                    new_rect = QRectF(self.drag_start_rect.left(), self.drag_start_rect.bottom() - new_h, new_w, new_h)
                elif self.drag_handle == 2: 
                    new_rect = QRectF(self.drag_start_rect.left(), self.drag_start_rect.top(), new_w, new_h)
                elif self.drag_handle == 3: 
                    new_rect = QRectF(self.drag_start_rect.right() - new_w, self.drag_start_rect.top(), new_w, new_h)
                    x1, y1 = self.to_video_coords(new_rect.topLeft())
                    x2, y2 = self.to_video_coords(new_rect.bottomRight())
                    threshold = 0.02
                    self.is_snapped_x = abs(((x1 + x2) / 2) - 0.5) < threshold
                    self.is_snapped_y = abs(((y1 + y2) / 2) - 0.5) < threshold
                    if self.is_snapped_x:
                        diff = 0.5 - ((x1 + x2) / 2)
                        x1 += diff; x2 += diff
                    if self.is_snapped_y:
                        diff = 0.5 - ((y1 + y2) / 2)
                        y1 += diff; y2 += diff
                    self.param_changed.emit("crop_x1", max(0.0, x1)); self.param_changed.emit("crop_y1", max(0.0, y1))
                    self.param_changed.emit("crop_x2", min(1.0, x2)); self.param_changed.emit("crop_y2", min(1.0, y2))
            else:
                if self.drag_handle == "move":
                    self.param_changed.emit("pos_x", self.drag_start_clip_pos[0] + dx_norm)
                    self.param_changed.emit("pos_y", self.drag_start_clip_pos[1] - dy_norm)
                elif isinstance(self.drag_handle, int):
                    scale_delta = dx_norm * 2.0 if self.drag_handle not in [0, 3] else -dx_norm * 2.0
                    new_s = max(0.1, self.drag_start_clip_scale[0] + scale_delta)
                    self.param_changed.emit("scale_x", new_s); self.param_changed.emit("scale_y", new_s)
            self.update()
        except Exception as e:
            self.dragging = False
            self.logger.error(f"[OVERLAY] Move Error: {e}")

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.interaction_ended.emit()
        self.dragging = False
        self.drag_handle = None

    def mouseDoubleClickEvent(self, event):
        self.parent().parent().parent().toggle_popout()

class PreviewWidget(QWidget):
    param_changed = pyqtSignal(str, float)
    interaction_started = pyqtSignal()
    interaction_ended = pyqtSignal()
    play_requested = pyqtSignal()
    seek_requested = pyqtSignal(float)

    def __init__(self, player_widget):
        super().__init__()
        self.player = player_widget
        self.popout_window = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.container = QWidget()
        l = QVBoxLayout(self.container)
        l.setContentsMargins(0,0,0,0)
        if self.player:
            l.addWidget(self.player)
        self.overlay = SafeOverlay(self.player if self.player else self.container)
        self.overlay.param_changed.connect(self.param_changed)
        self.overlay.interaction_started.connect(self.interaction_started)
        self.overlay.interaction_ended.connect(self.interaction_ended)
        self.popout_button = QPushButton("Pop Out", self.overlay)
        self.popout_button.setCursor(Qt.PointingHandCursor)
        self.popout_button.setToolTip("Pop Out")
        self.popout_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.popout_button.clicked.connect(self.toggle_popout)
        layout.addWidget(self.container)

    def set_player(self, player):
        self.player = player
        self.container.layout().addWidget(player)
        if not self.player.winId():
            self.player.createWinId()
        self.player.initialize_mpv(wid=int(self.player.winId()))
        self.overlay.setParent(self.player)
        self.overlay.raise_()
        self.overlay.show()
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(5, 5, 5, 5)
        btn_style_small = "QPushButton { background: #333; color: white; border: 1px solid #555; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #444; }"
        self.btn_rw = QPushButton("<< 5s")
        self.btn_rw.setCursor(Qt.PointingHandCursor)
        self.btn_rw.setToolTip("Rewind 5s")
        self.btn_rw.setFixedSize(60, 30)
        self.btn_rw.setStyleSheet(btn_style_small)
        self.btn_rw.clicked.connect(lambda: self.seek_requested.emit(-5.0))
        self.btn_play = QPushButton()
        self.btn_play.setFixedSize(480, 30)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setToolTip("Play/Pause")
        self.btn_play.clicked.connect(self.play_requested.emit)
        self.update_play_pause_button(False)
        self.btn_ff = QPushButton("5s >>")
        self.btn_ff.setCursor(Qt.PointingHandCursor)
        self.btn_ff.setToolTip("Fast-forward 5s")
        self.btn_ff.setFixedSize(60, 30)
        self.btn_ff.setStyleSheet(btn_style_small)
        self.btn_ff.clicked.connect(lambda: self.seek_requested.emit(5.0))
        ctrl_layout.addWidget(self.btn_rw)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_ff)
        self.layout().addLayout(ctrl_layout)

    def update_play_pause_button(self, is_playing):
        if is_playing:
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.btn_play.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {constants.COLOR_ERROR.name()}, stop:1 {constants.COLOR_ERROR.darker(150).name()});
                    color: white; font-size: 14px; font-weight: bold;
                    border: 1px solid {constants.COLOR_ERROR.darker(150).name()}; border-style: outset; border-radius: 2px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {constants.COLOR_ERROR.lighter(120).name()}, stop:1 {constants.COLOR_ERROR.name()});
                }}
                QPushButton:pressed {{ background: {constants.COLOR_ERROR.darker(150).name()}; border-style: inset; }}
            """)
        else:
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.btn_play.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {constants.COLOR_SUCCESS.name()}, stop:1 {constants.COLOR_SUCCESS.darker(150).name()});
                    color: white; font-size: 14px; font-weight: bold;
                    border: 1px solid {constants.COLOR_SUCCESS.darker(150).name()}; border-style: outset; border-radius: 2px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {constants.COLOR_SUCCESS.lighter(120).name()}, stop:1 {constants.COLOR_SUCCESS.name()});
                }}
                QPushButton:pressed {{ background: {constants.COLOR_SUCCESS.darker(150).name()}; border-style: inset; }}
            """)

    def set_mode(self, w, h, name):
        self.overlay.set_mode(w, h, name)

    def toggle_popout(self):
        if self.popout_window is None:
            self.popout_window = PopOutPlayerWindow(self.player, self)
            self.player.setParent(self.popout_window)
            if hasattr(self, 'mw') and self.mw:
                saved_geo = self.mw.config.get("popout_geometry")
                if saved_geo:
                    try:
                        x, y, w, h = map(int, saved_geo.split(','))
                        self.popout_window.setGeometry(x, y, w, h)
                    except:
                        self._apply_default_popout()
                else:
                    self._apply_default_popout()
            self.popout_window.show()
            self.popout_button.setText("Pop Back In")
            self.popout_button.setToolTip("Pop Back In")
            self.popout_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
        else:
            self.player.setParent(self.container)
            self.container.layout().addWidget(self.player)
            self.popout_window.close()
            self.popout_window = None
            self.popout_button.setText("Pop Out")
            self.popout_button.setToolTip("Pop Out")
            self.popout_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))

    def _apply_default_popout(self):
        """Defaults to 1700x850 on the secondary monitor if available."""
        desktop = QApplication.desktop()
        screen_count = desktop.screenCount()
        target_screen = 1 if screen_count > 1 else 0
        screen_rect = desktop.screenGeometry(target_screen)
        w, h = 1700, 850
        x = screen_rect.left() + (screen_rect.width() - w) // 2
        y = screen_rect.top() + (screen_rect.height() - h) // 2
        self.popout_window.setGeometry(x, y, w, h)