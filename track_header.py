from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDrag

class TrackHeaderWidget(QWidget):
    def __init__(self, track_name, track_idx, parent=None):
        super().__init__(parent)
        self.track_idx = track_idx
        self.setFixedWidth(120)
        self.setFixedHeight(40)
        layout = QVBoxLayout(self)
        self.track_name_label = QLabel(track_name)
        self.track_name_label.setAlignment(Qt.AlignCenter)
        self.mute_button = QPushButton("M")
        self.mute_button.setCheckable(True)
        self.mute_button.setToolTip("Mute Track")
        self.solo_button = QPushButton("S")
        self.solo_button.setCheckable(True)
        self.solo_button.setToolTip("Solo Track")
        self.lock_button = QPushButton("L")
        self.lock_button.setCheckable(True)
        self.lock_button.setToolTip("Lock Track")
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(self.mute_button)
        button_layout.addWidget(self.solo_button)
        button_layout.addWidget(self.lock_button)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.track_name_label)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.setStyleSheet("background-color: #3d3d3d; border-bottom: 1px solid #444;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(str(self.track_idx))
            drag.setMimeData(mime_data)
            drag.exec_(Qt.MoveAction)

class TrackHeaders(QWidget):
    tracks_reordered = pyqtSignal(int, int)
    def __init__(self, num_tracks=3, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 30, 0, 0)
        self.main_layout.setSpacing(0)
        self.headers = []
        for i in range(num_tracks):
            self.add_track_header(i)
        self.main_layout.addStretch()

    def add_track_header(self, idx):
        header = TrackHeaderWidget(f"Track {idx+1}", idx)
        self.main_layout.insertWidget(idx, header)
        self.headers.insert(idx, header)
        self.update_track_indices()

    def add_track(self):
        new_idx = len(self.headers)
        self.add_track_header(new_idx)

    def update_track_indices(self):
        for i, widget in enumerate(self.headers):
            widget.track_idx = i

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            source_idx = int(event.mimeData().text())
            
            # Determine target index based on where we dropped
            drop_pos = event.pos()
            child = self.childAt(drop_pos)
            
            # Walk up logic to find the widget with track_idx
            target_widget = None
            if child:
                # If we hit a button/label, get the parent container
                curr = child
                while curr:
                    if isinstance(curr, TrackHeaderWidget):
                        target_widget = curr
                        break
                    curr = curr.parent()
            
            # If dropped in empty space, assume end of list or ignore
            if target_widget is None:
                # Fallback: iterate heuristics or ignore
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
