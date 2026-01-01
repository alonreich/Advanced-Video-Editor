from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QRect

class SafeOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.mode = "Landscape"
        self.res = (1920, 1080)
        self.target_res = (1920, 1080)

    def paintEvent(self, e):
        if self.mode == "Landscape": return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        tw, th = self.target_res
        target_ar = tw / th
        current_ar = w / h
        if current_ar > target_ar:
            safe_h = h
            safe_w = int(h * target_ar)
            safe_x = (w - safe_w) // 2
            safe_y = 0
            p.fillRect(0, 0, safe_x, h, QColor(0, 0, 0, 128))
            p.fillRect(safe_x + safe_w, 0, w - (safe_x + safe_w), h, QColor(0, 0, 0, 128))
            p.setPen(QPen(Qt.white, 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(safe_x, safe_y, safe_w, safe_h)

class PreviewWidget(QWidget):
    def __init__(self, player_widget):
        super().__init__()
        self.player = player_widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.container = QWidget()
        l = QVBoxLayout(self.container)
        l.setContentsMargins(0,0,0,0)
        l.addWidget(self.player)
        self.overlay = SafeOverlay(self.player)
        layout.addWidget(self.container)

    def resizeEvent(self, event):
        self.overlay.resize(self.size())
        super().resizeEvent(event)

    def set_mode(self, width, height, mode_name):
        self.overlay.target_res = (width, height)
        self.overlay.mode = "Portrait" if "Portrait" in mode_name else "Landscape"
        self.overlay.update()
