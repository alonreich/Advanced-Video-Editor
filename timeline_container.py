import logging
from PyQt5.QtWidgets import QWidget, QHBoxLayout
from PyQt5.QtCore import pyqtSignal
from timeline_view import TimelineView
from track_header import TrackHeaders

class TimelineContainer(QWidget):
    time_updated = pyqtSignal(float)
    clip_selected = pyqtSignal(list)
    file_dropped = pyqtSignal(str, int, float)
    track_volume_changed = pyqtSignal(int, float)

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        from PyQt5.QtWidgets import QScrollArea
        from PyQt5.QtCore import Qt
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header_scroll = QScrollArea()
        self.header_scroll.setFixedWidth(120)
        self.header_scroll.setWidgetResizable(True)
        self.header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.header_scroll.setFrameShape(QScrollArea.NoFrame)

        self.track_headers = TrackHeaders()
        self.header_scroll.setWidget(self.track_headers)

        self.timeline_view = TimelineView(main_window=main_window, track_headers=self.track_headers)

        self.timeline_view.verticalScrollBar().valueChanged.connect(
            self.header_scroll.verticalScrollBar().setValue
        )

        self.main_layout.addWidget(self.header_scroll)
        self.main_layout.addWidget(self.timeline_view)
        self.timeline_view.time_updated.connect(self.time_updated)
        self.timeline_view.clip_selected.connect(self.clip_selected)
        self.timeline_view.file_dropped.connect(self.file_dropped)
        self.track_headers.tracks_reordered.connect(self.on_tracks_reordered)
        self.track_headers.track_volume_changed.connect(self.track_volume_changed)

    def on_tracks_reordered(self, old_idx, new_idx):
        self.timeline_view.reorder_tracks(old_idx, new_idx)

    def add_track(self):
        self.track_headers.add_track()
        self.timeline_view.add_track_to_scene()

    def remove_track(self):
        self.track_headers.remove_track()
        self.timeline_view.remove_track_from_scene()

    def update_tracks(self):
        """Maintains the expanding track rule based on occupied lanes."""
        clips = self.timeline_view.get_state()
        if not clips:
            highest_track = -1
        else:
            highest_track = max(c.get('track', 0) for c in clips)

        if highest_track < 1:
            desired_tracks = 2
        else:
            desired_tracks = min(highest_track + 2, 50)
        current_tracks = self.timeline_view.num_tracks
        while current_tracks < desired_tracks:
            self.add_track()
            current_tracks += 1
        while current_tracks > desired_tracks:
            self.remove_track()
            current_tracks -= 1

    def set_visual_time(self, sec):
        """Passes the visual update to the view without emitting signals."""
        self.timeline_view.set_visual_time(sec)

    def load_state(self, state):
        self.track_headers.clear_all_headers()
        self.timeline_view.scene.clear()
        self.timeline_view.set_num_tracks(0) 
        try:
            self.timeline_view.load_state(state or [])
            self.update_tracks()
        except Exception as e:
            self.logger.error(f"Timeline Load Error: {e}")

    def __getattr__(self, name):
        """Proxy unknown attributes to timeline_view."""
        if hasattr(self.timeline_view, name):
            return getattr(self.timeline_view, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")