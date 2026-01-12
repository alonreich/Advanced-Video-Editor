from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QSlider
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDrag
import constants

class TrackHeaderWidget(QWidget):
    volume_changed = pyqtSignal(int, float)

    def __init__(self, track_name, track_idx, parent=None):
        super().__init__(parent)
        self.track_idx = track_idx
        self.setFixedWidth(120)
        self.setFixedHeight(constants.TRACK_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        self.track_name_label = QLabel(track_name)
        self.track_name_label.setAlignment(Qt.AlignCenter)
        self.track_name_label.setStyleSheet("color: #ccc; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.track_name_label)
        self.setLayout(layout)
        self.setStyleSheet("background-color: #3d3d3d; border-bottom: 1px solid #444; border-right: 1px solid #222;")
        self.is_selected = False

    def set_selected(self, selected):
        self.is_selected = selected
        if selected:
            self.setStyleSheet("background-color: #3d3d3d; border: 2px solid yellow; border-bottom: 1px solid #444; border-right: 1px solid #222;")
        else:
            self.setStyleSheet("background-color: #3d3d3d; border-bottom: 1px solid #444; border-right: 1px solid #222;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.track_idx))
            drag.setMimeData(mime_data)
            drag.exec_(Qt.MoveAction)

class TrackHeaders(QWidget):
    tracks_reordered = pyqtSignal(int, int)
    track_volume_changed = pyqtSignal(int, float)

    def __init__(self, num_tracks=2, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, constants.RULER_HEIGHT, 0, 0)
        self.main_layout.setSpacing(0)
        self.headers = []
        for i in range(num_tracks):
            self.add_track_header(i)
        self.main_layout.addStretch()

    def set_selected(self, track_idx):
        for i, header in enumerate(self.headers):
            header.set_selected(i == track_idx)

    def add_track_header(self, idx):
        header = TrackHeaderWidget(f"Track {idx+1}", idx)
        header.volume_changed.connect(self.on_track_vol_changed)
        self.main_layout.insertWidget(idx, header)
        self.headers.insert(idx, header)
        self.update_track_indices()

    def on_track_vol_changed(self, track_idx, val):
        try:
            self.track_volume_changed.emit(track_idx, val)
        except: pass

    def add_track(self):
        new_idx = len(self.headers)
        self.add_track_header(new_idx)

    def remove_track(self):
        if not self.headers:
            return
        header_to_remove = self.headers.pop()
        self.main_layout.removeWidget(header_to_remove)
        header_to_remove.deleteLater()
        self.update_track_indices()

    def update_track_indices(self):
        for i, widget in enumerate(self.headers):
            widget.track_idx = i

    def clear_all_headers(self):
        """Properly nukes all track widgets and resets the list."""
        while self.main_layout.count() > 0:
            item = self.main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.headers = []
        self.main_layout.addStretch()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            source_idx = int(event.mimeData().text())
            drop_pos = event.pos()
            child = self.childAt(drop_pos)
            target_widget = None
            if child:
                curr = child
                while curr:
                    if isinstance(curr, TrackHeaderWidget):
                        target_widget = curr
                        break
                    curr = curr.parent()
            if target_widget is None:
                return
            target_idx = target_widget.track_idx
            if source_idx != target_idx:
                source_widget = self.headers.pop(source_idx)
                self.headers.insert(target_idx, source_widget)
                self.update_track_indices()
                self.tracks_reordered.emit(source_idx, target_idx)
            event.accept()
        else:
            event.ignore()