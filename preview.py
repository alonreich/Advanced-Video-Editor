from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QRect, QPointF, QRectF, pyqtSignal, QTimer

class PopOutPlayerWindow(QWidget):
    def __init__(self, player_widget, preview_widget):
        super().__init__()
        self.player = player_widget
        self.preview_widget = preview_widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        snap_back_button = QPushButton("Snap Back")
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

    def __init__(self, parent):
        super().__init__(parent)
        self.selected_clip = None
        self.crop_mode = False
        self.dragging = False
        self.drag_handle = None
        self.drag_start_pos = QPointF()
        self.drag_start_rect = QRectF()
        self.drag_start_crop = None
        self.drag_start_clip_pos = (0,0)
        self.drag_start_clip_scale = (1,1)
        self.transform_rect = QRectF()
        self.crop_rect = QRectF()
        self.handles = []
        self.handle_size = 10
        self.dash_offset = 0
        self.dash_timer = QTimer(self)
        self.dash_timer.timeout.connect(self.update_dash_offset)
        self.dash_timer.start(100)

    def update_dash_offset(self):
        self.dash_offset = (self.dash_offset + 1) % 10
        self.update()

    def set_selected_clip(self, clip_model):
        self.selected_clip = clip_model
        self.update()

    def toggle_crop_mode(self):
        self.crop_mode = not self.crop_mode
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self.selected_clip: return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.crop_mode:
            self.draw_crop_controls(p)
        else:
            self.draw_transform_controls(p)

    def draw_transform_controls(self, p):
        w, h = self.width(), self.height()
        sx, sy = self.selected_clip.scale_x, self.selected_clip.scale_y
        px, py = self.selected_clip.pos_x, self.selected_clip.pos_y
        rect_w = w * sx
        rect_h = h * sy
        rect_x = (w - rect_w) / 2 + px * w
        rect_y = (h - rect_h) / 2 - py * h
        self.transform_rect = QRectF(rect_x, rect_y, rect_w, rect_h)
        p.setPen(QPen(QColor(0, 150, 255), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.transform_rect)
        self.update_handles()
        p.setBrush(QColor(0, 150, 255))
        for handle in self.handles:
            p.drawRect(handle)

    def draw_crop_controls(self, p):
        pen = QPen(Qt.yellow, 2, Qt.CustomDashLine)
        pen.setDashPattern([5, 5])
        pen.setDashOffset(self.dash_offset)
        p.setPen(pen)
        if not self.crop_rect.isNull():
            p.drawRect(self.crop_rect)

    def update_handles(self):
        self.handles = []
        r = self.transform_rect
        hs = self.handle_size
        self.handles.append(QRectF(r.left() - hs/2, r.top() - hs/2, hs, hs))
        self.handles.append(QRectF(r.right() - hs/2, r.top() - hs/2, hs, hs))
        self.handles.append(QRectF(r.right() - hs/2, r.bottom() - hs/2, hs, hs))
        self.handles.append(QRectF(r.left() - hs/2, r.bottom() - hs/2, hs, hs))

    def mousePressEvent(self, event):
        if not self.selected_clip: return
        if self.crop_mode:
            self.dragging = True
            self.drag_start_pos = event.pos()
            self.crop_rect = QRectF(self.drag_start_pos, self.drag_start_pos)
            self.update()
            return
        for i, handle in enumerate(self.handles):
            if handle.contains(event.pos()):
                self.dragging = True
                self.drag_handle = i
                self.drag_start_pos = event.pos()
                self.drag_start_rect = QRectF(self.transform_rect)
                self.drag_start_clip_scale = (self.selected_clip.scale_x, self.selected_clip.scale_y)
                self.drag_start_clip_pos = (self.selected_clip.pos_x, self.selected_clip.pos_y)
                return
        if self.transform_rect.contains(event.pos()):
            self.dragging = True
            self.drag_handle = "move"
            self.drag_start_pos = event.pos()
            self.drag_start_clip_pos = (self.selected_clip.pos_x, self.selected_clip.pos_y)

    def mouseMoveEvent(self, event):
        if not self.dragging: return
        if self.crop_mode:
            self.crop_rect = QRectF(self.drag_start_pos, event.pos()).normalized()
            self.update()
            return
        if self.drag_handle == "move":
            delta = event.pos() - self.drag_start_pos
            w, h = self.width(), self.height()
            if w > 0 and h > 0:
                new_px = self.drag_start_clip_pos[0] + delta.x() / w
                new_py = self.drag_start_clip_pos[1] - delta.y() / h
                self.param_changed.emit("pos_x", new_px)
                self.param_changed.emit("pos_y", new_py)
        elif isinstance(self.drag_handle, int):
            delta = event.pos() - self.drag_start_pos
            new_rect = QRectF(self.drag_start_rect)
            if self.drag_handle == 0:
                new_rect.setTopLeft(self.drag_start_rect.topLeft() + delta)
            elif self.drag_handle == 1:
                new_rect.setTopRight(self.drag_start_rect.topRight() + delta)
            elif self.drag_handle == 2:
                new_rect.setBottomRight(self.drag_start_rect.bottomRight() + delta)
            elif self.drag_handle == 3:
                new_rect.setBottomLeft(self.drag_start_rect.bottomLeft() + delta)
            w, h = self.width(), self.height()
            if w > 0 and h > 0:
                new_sx = new_rect.width() / w
                new_sy = new_rect.height() / h
                new_px = self.drag_start_clip_pos[0] + (new_rect.center().x() - self.drag_start_rect.center().x()) / w
                new_py = self.drag_start_clip_pos[1] - (new_rect.center().y() - self.drag_start_rect.center().y()) / h
                self.param_changed.emit("scale_x", new_sx)
                self.param_changed.emit("scale_y", new_sy)
                self.param_changed.emit("pos_x", new_px)
                self.param_changed.emit("pos_y", new_py)
        self.update()

    def mouseReleaseEvent(self, event):
        if self.crop_mode and self.dragging:
            w, h = self.width(), self.height()
            if w > 0 and h > 0:
                self.param_changed.emit("crop_x1", self.crop_rect.left() / w)
                self.param_changed.emit("crop_y1", self.crop_rect.top() / h)
                self.param_changed.emit("crop_x2", self.crop_rect.right() / w)
                self.param_changed.emit("crop_y2", self.crop_rect.bottom() / h)
            self.crop_rect = QRectF()
        self.dragging = False
        self.drag_handle = None

    def mouseDoubleClickEvent(self, event):
        self.parent().parent().parent().toggle_popout()

class PreviewWidget(QWidget):
    param_changed = pyqtSignal(str, float)
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
        l.addWidget(self.player)
        self.overlay = SafeOverlay(self.player)
        self.overlay.param_changed.connect(self.param_changed)
        self.popout_button = QPushButton("Pop Out", self.overlay)
        self.popout_button.clicked.connect(self.toggle_popout)
        layout.addWidget(self.container)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(5, 5, 5, 5)
        btn_style_small = "QPushButton { background: #333; color: white; border: 1px solid #555; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #444; }"
        self.btn_rw = QPushButton("<< 5s")
        self.btn_rw.setFixedSize(60, 36)
        self.btn_rw.setStyleSheet(btn_style_small)
        self.btn_rw.clicked.connect(lambda: self.seek_requested.emit(-5.0))
        self.btn_play = QPushButton("PLAY / PAUSE")
        self.btn_play.setFixedSize(240, 36)
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
        self.btn_ff.setFixedSize(60, 42)
        self.btn_ff.setStyleSheet(btn_style_small)
        self.btn_ff.clicked.connect(lambda: self.seek_requested.emit(5.0))
        ctrl_layout.addWidget(self.btn_rw)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_ff)
        layout.addLayout(ctrl_layout)

    def toggle_popout(self):
        if self.popout_window is None:
            self.popout_window = PopOutPlayerWindow(self.player, self)
            self.player.setParent(self.popout_window)
            self.popout_window.show()
        else:
            self.player.setParent(self.container)
            self.container.layout().addWidget(self.player)
            self.popout_window.close()
            self.popout_window = None

    def resizeEvent(self, event):
        self.overlay.resize(self.size())
        super().resizeEvent(event)

    def set_mode(self, width, height, mode_name):
        self.overlay.target_res = (width, height)
        self.overlay.mode = "Portrait" if "Portrait" in mode_name else "Landscape"
        self.overlay.update()
