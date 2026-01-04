from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QStyle
from PyQt5.QtGui import QPainter, QColor, QPen, QRegion
from PyQt5.QtCore import Qt, QRect, QPointF, QRectF, pyqtSignal, QTimer

class PopOutPlayerWindow(QWidget):
    def __init__(self, player_widget, preview_widget):
        super().__init__()
        self.player = player_widget
        self.preview_widget = preview_widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        snap_back_button = QPushButton("Pop In")
        snap_back_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
        snap_back_button.clicked.connect(self.preview_widget.toggle_popout)
        layout.addWidget(self.player)
        layout.addWidget(snap_back_button)
        self.setWindowTitle("Preview")
        self.resize(1280, 720)

    def closeEvent(self, event):
        self.preview_widget.toggle_popout()
        event.accept()

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
        self.handle_size = 10
        self.dash_offset = 0
        self.is_recording = False
        self.target_res = (1920, 1080)
        self.mode = "Landscape"
        self.dash_timer = QTimer(self)
        self.dash_timer.timeout.connect(self.update_dash_offset)
        self.dash_timer.start(100)

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
        self.update()

    def get_video_rect(self):
        w, h = self.width(), self.height()
        target_w, target_h = self.target_res
        if target_w == 0 or target_h == 0: return self.rect()
        if self.mode == "Portrait":
            scale = min(h / target_h, w / target_w)
            nw, nh = target_w * scale, target_h * scale
        else:
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
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        v_rect = self.get_video_rect()
        if self.mode == "Portrait":
            self.draw_portrait_guides(p, v_rect)
        if self.is_recording:
            p.setBrush(QColor(255, 0, 0))
            p.setPen(Qt.NoPen)
            if (self.dash_offset // 2) % 2 == 0:
                p.drawEllipse(20, 20, 15, 15)
                p.setPen(QPen(Qt.white, 1))
                p.drawText(40, 32, "REC")
        if not self.selected_clip: return
        p.setClipRect(v_rect)
        if self.crop_mode:
            self.draw_crop_controls(p, v_rect)
        else:
            self.draw_transform_controls(p, v_rect)

    def draw_portrait_guides(self, p, v_rect):
        """Goal 10: Dim out-of-bounds media at 50% transparency."""
        widget_rect = self.rect()
        p.save()
        from PyQt5.QtGui import QPainterPath
        path = QPainterPath()
        path.addRect(QRectF(widget_rect))
        path.addRect(v_rect)
        p.setClipPath(path)
        p.fillRect(widget_rect, QColor(0, 0, 0, 128)) 
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 150), 2, Qt.DashLine))
        p.drawRect(v_rect)
        p.setPen(QPen(QColor(255, 255, 255, 100), 2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(v_rect)

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
        """Goal 16: Real-time coordinate transformation for visual transforms."""
        try:
            if not self.dragging or not self.selected_clip: 
                return
            v_rect = self.get_video_rect()
            if v_rect.width() == 0 or v_rect.height() == 0: 
                return
            delta = event.pos() - self.drag_start_pos
            dx_norm = delta.x() / v_rect.width()
            dy_norm = delta.y() / v_rect.height()
            if self.drag_handle == "move":
                new_px = self.drag_start_clip_pos[0] + dx_norm
                new_py = self.drag_start_clip_pos[1] - dy_norm
                self.param_changed.emit("pos_x", new_px)
                self.param_changed.emit("pos_y", new_py)
            elif isinstance(self.drag_handle, int):
                scale_delta = dx_norm * 2.0 
                if self.drag_handle in [0, 3]:
                    scale_delta = -scale_delta
                new_sx = max(0.1, self.drag_start_clip_scale[0] + scale_delta)
                new_sy = max(0.1, self.drag_start_clip_scale[1] + scale_delta)
                self.param_changed.emit("scale_x", new_sx)
                self.param_changed.emit("scale_y", new_sy)
            self.update()
        except Exception as e:
            self.dragging = False
            self.drag_handle = None
            self.logger.error(f"[OVERLAY] Move Error: {e}")
            if self.crop_mode:
                if self.drag_handle == "crop_draw":
                    start_x, start_y = self.to_video_coords(self.drag_start_pos)
                    curr_x, curr_y = self.to_video_coords(event.pos())
                    start_x = max(0.0, min(1.0, start_x))
                    start_y = max(0.0, min(1.0, start_y))
                    curr_x = max(0.0, min(1.0, curr_x))
                    curr_y = max(0.0, min(1.0, curr_y))
                    x1 = min(start_x, curr_x)
                    y1 = min(start_y, curr_y)
                    x2 = max(start_x, curr_x)
                    y2 = max(start_y, curr_y)
                    if (x2 - x1) > 0.05 and (y2 - y1) > 0.05:
                        self.param_changed.emit("crop_x1", x1)
                        self.param_changed.emit("crop_y1", y1)
                        self.param_changed.emit("crop_x2", x2)
                        self.param_changed.emit("crop_y2", y2)
                    self.update()
                    return
                elif isinstance(self.drag_handle, int):
                    delta = event.pos() - self.drag_start_pos
                    new_rect = QRectF(self.drag_start_rect)
                    aspect_ratio = self.target_res[0] / self.target_res[1]
                    if self.drag_handle == 0:
                        new_rect.setTopLeft(new_rect.topLeft() + delta)
                        new_rect.setWidth(new_rect.height() * aspect_ratio)
                    elif self.drag_handle == 1:
                        new_rect.setTopRight(new_rect.topRight() + delta)
                        new_rect.setWidth(new_rect.height() * aspect_ratio)
                    elif self.drag_handle == 2:
                        new_rect.setBottomRight(new_rect.bottomRight() + delta)
                        new_rect.setWidth(new_rect.height() * aspect_ratio)
                    elif self.drag_handle == 3:
                        new_rect.setBottomLeft(new_rect.bottomLeft() + delta)
                        new_rect.setWidth(new_rect.height() * aspect_ratio)
                    x1, y1 = self.to_video_coords(new_rect.topLeft())
                    x2, y2 = self.to_video_coords(new_rect.bottomRight())
                    self.param_changed.emit("crop_x1", x1)
                    self.param_changed.emit("crop_y1", y1)
                    self.param_changed.emit("crop_x2", x2)
                    self.param_changed.emit("crop_y2", y2)
                    self.update()
                    return
            delta = event.pos() - self.drag_start_pos
            dx_norm = delta.x() / v_rect.width()
            dy_norm = delta.y() / v_rect.height()
            if self.drag_handle == "move":
                new_px = self.drag_start_clip_pos[0] + dx_norm
                new_py = self.drag_start_clip_pos[1] - dy_norm
                self.param_changed.emit("pos_x", new_px)
                self.param_changed.emit("pos_y", new_py)
            elif isinstance(self.drag_handle, int):
                scale_delta = dx_norm
                if self.drag_handle in [0, 3]: scale_delta = -scale_delta
                new_sx = max(0.1, self.drag_start_clip_scale[0] + scale_delta)
                new_sy = max(0.1, self.drag_start_clip_scale[1] + scale_delta)
                self.param_changed.emit("scale_x", new_sx)
                self.param_changed.emit("scale_y", new_sy)
            self.update()
        except Exception as e:
            self.dragging = False
            self.drag_handle = None
            print(f"Error in mouseMoveEvent: {e}")

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
        self.popout_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.popout_button.clicked.connect(self.toggle_popout)
        layout.addWidget(self.container)

    def set_player(self, player):
        self.player = player
        self.container.layout().addWidget(player)
        self.overlay.setParent(player)
        self.overlay.resize(player.size())
        self.overlay.show()
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(5, 5, 5, 5)
        btn_style_small = "QPushButton { background: #333; color: white; border: 1px solid #555; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #444; }"
        self.btn_rw = QPushButton("<< 5s")
        self.btn_rw.setFixedSize(60, 30)
        self.btn_rw.setStyleSheet(btn_style_small)
        self.btn_rw.clicked.connect(lambda: self.seek_requested.emit(-5.0))
        self.btn_play = QPushButton("PLAY / PAUSE")
        self.btn_play.setFixedSize(480, 30)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self.play_requested.emit)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2E7D32, stop:1 #1B5E20);
                color: white; font-size: 14px; font-weight: bold;
                border: 1px solid #1B5E20; border-style: outset; border-radius: 2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #43A047, stop:1 #2E7D32);
            }
            QPushButton:pressed { background: #1B5E20; border-style: inset; }
        """)
        self.btn_ff = QPushButton("5s >>")
        self.btn_ff.setFixedSize(60, 30)
        self.btn_ff.setStyleSheet(btn_style_small)
        self.btn_ff.clicked.connect(lambda: self.seek_requested.emit(5.0))
        ctrl_layout.addWidget(self.btn_rw)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_ff)
        self.layout().addLayout(ctrl_layout)

    def toggle_popout(self):
        if self.popout_window is None:
            self.popout_window = PopOutPlayerWindow(self.player, self)
            self.player.setParent(self.popout_window)
            self.popout_window.show()
            self.popout_button.setText("Pop In")
            self.popout_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
        else:
            self.player.setParent(self.container)
            self.container.layout().addWidget(self.player)
            self.popout_window.close()
            self.popout_window = None
            self.popout_button.setText("Pop Out")
            self.popout_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))

    def resizeEvent(self, event):
        self.overlay.resize(self.size())
        super().resizeEvent(event)

    def set_mode(self, width, height, mode_name):
        self.overlay.set_mode(width, height, mode_name)
